"""
E2E tests expect a running API. Uvicorn with multiple workers can delay the first responses.
"""

import os
import time

import pytest
import requests

# Prefer IPv4 on Windows so requests hit the published Docker port reliably.
E2E_BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def wait_for_backend_ready():
    deadline = time.time() + 120
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{E2E_BASE_URL}/health", timeout=3)
            if r.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(1)
    msg = (
        f"Backend did not become ready at {E2E_BASE_URL}/health (last error: {last_err!r})"
    )
    # CI must fail if the server step did not start; local full-suite runs skip live HTTP E2E.
    if os.environ.get("CI") == "true" or os.environ.get("E2E_REQUIRE_LIVE_SERVER") == "1":
        pytest.fail(msg)
    pytest.skip(msg + " (start: uvicorn app.main:app --host 127.0.0.1 --port 8000)")
