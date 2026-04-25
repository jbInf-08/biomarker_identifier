"""
AWS Lambda entrypoint (Mangum ASGI adapter).

Deploy with `handler.handler` as the Lambda function; set PYTHONPATH to include `backend`.
"""

try:
    from mangum import Mangum
except ImportError as e:
    raise ImportError(
        "Install mangum in the Lambda package: pip install mangum"
    ) from e

from app.main import app

handler = Mangum(app, lifespan="off")
