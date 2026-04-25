"""
Request-scoped tenant context middleware.

This provides a minimal implementation for attaching a `tenant_id` to the
request state based on a header. It serves as the foundation for the
Week 5 multi-tenant architecture by allowing route handlers and services
to apply tenant-aware filtering.
"""

from typing import Callable

from fastapi import Request


class TenantContextMiddleware:
    def __init__(self, app, header_name: str = "X-Tenant-ID"):
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def receive_wrapper():
            message = await receive()
            return message

        request = Request(scope, receive=receive_wrapper)
        tenant_id = request.headers.get(self.header_name)
        # Store tenant_id on scope for later retrieval via `request.state`
        scope.setdefault("state", {})
        scope["state"]["tenant_id"] = tenant_id

        await self.app(scope, receive, send)
