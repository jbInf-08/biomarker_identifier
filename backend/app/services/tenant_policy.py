"""
Tenant vs admin access policy helpers (collaboration + scoped APIs).

- **Admin** (``user.role == "admin"``) may list cross-tenant resources when explicitly allowed.
- **Researcher** with `tenant_id` is restricted to matching `tenant_id` on resources.
"""

from typing import Any, Optional

from app.models.user_model import User


def is_platform_admin(user: User) -> bool:
    return getattr(user, "role", None) == "admin"


def effective_tenant_filter(user: User) -> Optional[str]:
    """Return tenant id to filter by, or None if no tenant scope."""
    tid = getattr(user, "tenant_id", None)
    return str(tid).strip() if tid else None


def admin_may_bypass_tenant(user: User) -> bool:
    """When True, list endpoints may omit tenant filter (audit logged at route)."""
    return is_platform_admin(user)


def enforce_resource_tenant(resource_tenant_id: Optional[str], user: User) -> None:
    """
    Raise PermissionError when ``resource_tenant_id`` conflicts with user's tenant scope.
    """
    if is_platform_admin(user):
        return
    ut = effective_tenant_filter(user)
    if ut and resource_tenant_id is not None and str(resource_tenant_id) != str(ut):
        raise PermissionError("resource tenant does not match authenticated tenant")


def apply_tenant_scope(query: Any, model: Any, user: User):
    """
    Apply ``model.tenant_id`` scoping when user has tenant context and is not admin.
    """
    if is_platform_admin(user):
        return query
    ut = effective_tenant_filter(user)
    if not ut or not hasattr(model, "tenant_id"):
        return query
    return query.filter(getattr(model, "tenant_id") == ut)
