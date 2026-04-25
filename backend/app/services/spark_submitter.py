"""
Spark job submission wrapper for production/offline heavy workloads.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from typing import Dict, List, Optional

from app.core.config import settings


def spark_available() -> bool:
    return bool(shutil.which(settings.SPARK_SUBMIT_BIN))


def submit_spark_job(
    *,
    app_path: str,
    app_args: Optional[List[str]] = None,
    conf: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Submit a spark application and return process metadata.

    This is non-blocking: it starts `spark-submit` and returns PID + command.
    """
    if not settings.SPARK_ENABLED:
        raise RuntimeError("Spark integration is disabled (SPARK_ENABLED=false)")
    if not spark_available():
        raise RuntimeError(
            f"spark-submit binary not found: {settings.SPARK_SUBMIT_BIN}"
        )

    cmd = [
        settings.SPARK_SUBMIT_BIN,
        "--master",
        settings.SPARK_MASTER_URL,
        "--deploy-mode",
        settings.SPARK_DEPLOY_MODE,
    ]
    for k, v in (conf or {}).items():
        cmd.extend(["--conf", f"{k}={v}"])
    cmd.append(app_path)
    cmd.extend(app_args or [])

    proc = subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "pid": str(proc.pid),
        "command": " ".join(shlex.quote(p) for p in cmd),
        "master": settings.SPARK_MASTER_URL,
        "deploy_mode": settings.SPARK_DEPLOY_MODE,
    }
