# Runbook: application alerts (baseline)

## LLM errors spike

1. Check `/api/analysis/llm/status` — transformers install and `OPENAI_API_KEY`.
2. Inspect logs for `LLM` / `OpenAI` warnings.
3. Verify GPU/CPU memory if using local models.

## Federated rounds failing

1. Confirm `min_participants` vs number of `updates` per `round_id`.
2. Check DB for `federated_models` rows with matching `round_id`.
3. Review `docs/federated_threat_model.md` for deployment constraints.

## High HTTP latency

1. Check `/metrics` — `http_request_duration_seconds` and `llm_request_duration_seconds`.
2. Scale workers; ensure DB connection pool healthy.

## Pipeline stuck

1. Query run `status` and `progress_percent` from `/api/biomarkers/runs/{id}/status`.
2. If Celery is used, verify `celery_task_id` in run `configuration` and worker connectivity to Redis.
