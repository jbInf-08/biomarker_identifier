# Serverless (AWS Lambda) adapter

Run the FastAPI app behind API Gateway using [Mangum](https://github.com/jordaneremieff/mangum).

1. Package the backend with dependencies (same as Docker image build context under `backend/`).
2. Set handler to `handler.handler` (see `handler.py`).
3. Configure env vars (`SECRET_KEY`, `DATABASE_URL`, etc.) in Lambda.
4. Set **`PYTHONPATH`** to the directory that contains the `app` package (the `backend/` folder), or place `handler.py` inside `backend/` next to `app/`.

This is an **optional** deployment shape; the canonical stack remains Docker/Kubernetes.

```bash
cd backend
pip install mangum -r requirements-prod.txt
# zip site-packages + app/ + deployment/serverless/handler.py (or copy handler into backend/)
```

See `template.yaml` for a minimal AWS SAM sketch.
