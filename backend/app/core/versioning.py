"""
API versioning helpers.

This module provides a simple helper for reading the requested API version
from headers and a list of supported versions, matching the Week 9
description of v1/v2 versioning.
"""

from typing import List

from fastapi import Header

SUPPORTED_API_VERSIONS: List[str] = ["v1", "v2"]
DEFAULT_API_VERSION: str = "v1"


async def get_api_version(x_api_version: str | None = Header(default=None)) -> str:
    """
    Dependency that resolves the requested API version.

    - Reads the `X-API-Version` header (e.g., `v1`, `v2`)
    - Falls back to `DEFAULT_API_VERSION` if not provided or unsupported
    """
    if x_api_version in SUPPORTED_API_VERSIONS:
        return x_api_version
    return DEFAULT_API_VERSION
