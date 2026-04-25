"""
HTTP delivery for WebhookSubscription rows (run lifecycle and integrations).

Retries with exponential backoff; idempotency keys avoid duplicate successful sends;
failed deliveries are recorded (DLQ-style ``dead`` status after max attempts).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models.platform_models import WebhookDeliveryLog, WebhookSubscription

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 5


def _canonical_body(event: str, payload: Dict[str, Any]) -> bytes:
    body_obj = {"event": event, **payload}
    return json.dumps(body_obj, sort_keys=True, default=str).encode("utf-8")


def dispatch_webhooks_for_user(
    db: Session,
    *,
    user_id: UUID,
    event: str,
    payload: Dict[str, Any],
) -> None:
    """POST JSON to each active webhook subscribed to ``event``."""
    rows = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.user_id == user_id,
            WebhookSubscription.is_active == True,  # noqa: E712
        )
        .all()
    )
    if not rows:
        return

    body = _canonical_body(event, payload)
    payload_hash = hashlib.sha256(body).hexdigest()
    idempotency_key = hashlib.sha256(f"{event}:{payload_hash}".encode()).hexdigest()

    for row in rows:
        evs = row.events if row.events else ["run.completed", "run.failed"]
        if event not in evs:
            continue

        prior = (
            db.query(WebhookDeliveryLog)
            .filter(
                WebhookDeliveryLog.webhook_id == row.id,
                WebhookDeliveryLog.idempotency_key == idempotency_key,
            )
            .first()
        )
        if (
            prior
            and prior.status == "sent"
            and prior.http_status is not None
            and 200 <= prior.http_status < 400
        ):
            logger.info("webhook idempotent skip %s %s", event, row.url)
            continue

        log_row = prior or WebhookDeliveryLog(
            webhook_id=row.id,
            user_id=user_id,
            event=event,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            status="pending",
            attempts=0,
        )
        if not prior:
            db.add(log_row)
            db.flush()

        secret = (row.secret or "").encode("utf-8")
        sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={sig}",
            "X-Webhook-Event": event,
            "X-Webhook-Idempotency-Key": idempotency_key,
        }

        sent = False
        last_err: str | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                r = httpx.post(str(row.url), content=body, headers=headers, timeout=20.0)
                log_row.attempts = attempt + 1
                log_row.http_status = r.status_code
                if 200 <= r.status_code < 400:
                    log_row.status = "sent"
                    log_row.last_error = None
                    sent = True
                    logger.info(
                        "webhook %s -> %s status=%s attempt=%s",
                        event,
                        row.url,
                        r.status_code,
                        attempt + 1,
                    )
                    break
                last_err = f"HTTP {r.status_code}"
                log_row.last_error = last_err
                if r.status_code < 500:
                    break
            except Exception as e:
                last_err = str(e)
                log_row.attempts = attempt + 1
                log_row.last_error = last_err
                logger.warning(
                    "webhook delivery error %s attempt %s: %s",
                    row.url,
                    attempt + 1,
                    e,
                )
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(min(2**attempt, 16))

        if not sent:
            log_row.status = "dead" if log_row.attempts >= _MAX_ATTEMPTS else "failed"
            if not log_row.last_error:
                log_row.last_error = last_err

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("webhook log commit failed: %s", e)
