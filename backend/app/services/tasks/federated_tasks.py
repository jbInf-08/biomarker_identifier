"""
Optional Celery tasks for federated round orchestration (hook for Flower / workers).
"""

import logging

from app.services.celery_service import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="federated.aggregate_round")
def aggregate_federated_round(round_id: str) -> dict:
    """
    Example: aggregate a round asynchronously. Wire from your scheduler or Flower.
    """
    import asyncio

    from app.services.federated_learning_service import federated_learning_service

    async def _run():
        return await federated_learning_service.aggregate_models(round_id)

    return asyncio.run(_run())
