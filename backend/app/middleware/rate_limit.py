"""
Shared SlowAPI limiter — same instance must be on app.state.limiter.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _limiter_enabled() -> bool:
    """False only when explicitly disabling (1/true/yes); 0/false/no/unset keeps limits on."""
    v = (os.environ.get("BIOMARKER_DISABLE_RATE_LIMIT") or "").lower()
    return v not in ("1", "true", "yes")


limiter = Limiter(key_func=get_remote_address, enabled=_limiter_enabled())
