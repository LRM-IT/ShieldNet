from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.api.dependencies.plugin_runtime import (
    ActivePluginRuntime,
)
from app.services.plugin_rate_limit_service import (
    plugin_rate_limiter,
)


async def enforce_plugin_rate_limit(
    *,
    request: Request,
    active: ActivePluginRuntime,
    scope: str,
) -> None:
    result = await plugin_rate_limiter.check(
        guild_id=active.claims.guild_id,
        plugin_key=active.claims.plugin_key,
        scope=scope,
    )

    request.state.plugin_audit_rate_limit_scope = scope
    request.state.plugin_audit_rate_limit = result.limit
    request.state.plugin_audit_rate_remaining = (
        result.remaining
    )
    request.state.plugin_audit_rate_reset = (
        result.reset_after
    )

    if result.allowed:
        return

    request.state.plugin_audit_error = (
        f"Plugin API rate limit exceeded: {scope}"
    )

    retry_after = max(
        1,
        int(result.retry_after + 0.999),
    )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Plugin API rate limit exceeded "
            f"for scope '{scope}'"
        ),
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset-After": (
                f"{result.reset_after:.3f}"
            ),
        },
    )
