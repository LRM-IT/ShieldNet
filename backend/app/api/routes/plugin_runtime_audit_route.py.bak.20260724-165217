from __future__ import annotations

import time
from collections.abc import Callable
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute

from app.services.plugin_api_audit_service import (
    PluginApiAuditEvent,
    PluginApiAuditService,
)


class PluginRuntimeAuditRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def audited_handler(
            request: Request,
        ) -> Response:
            started = time.perf_counter()

            incoming_request_id = request.headers.get(
                "X-Request-ID",
                "",
            ).strip()

            request_id = (
                incoming_request_id[:64]
                if incoming_request_id
                else str(uuid4())
            )

            request.state.plugin_audit_request_id = (
                request_id
            )

            status_code = 500
            error_detail: str | None = None
            response: Response | None = None

            try:
                response = await original_handler(request)
                status_code = response.status_code

                rate_limit = getattr(
                    request.state,
                    "plugin_audit_rate_limit",
                    None,
                )

                rate_remaining = getattr(
                    request.state,
                    "plugin_audit_rate_remaining",
                    None,
                )

                rate_reset = getattr(
                    request.state,
                    "plugin_audit_rate_reset",
                    None,
                )

                if rate_limit is not None:
                    response.headers[
                        "X-RateLimit-Limit"
                    ] = str(rate_limit)

                if rate_remaining is not None:
                    response.headers[
                        "X-RateLimit-Remaining"
                    ] = str(rate_remaining)

                if rate_reset is not None:
                    response.headers[
                        "X-RateLimit-Reset-After"
                    ] = f"{rate_reset:.3f}"

                response.headers[
                    "X-Request-ID"
                ] = request_id

                return response

            except HTTPException as exc:
                status_code = exc.status_code

                if isinstance(exc.detail, str):
                    error_detail = exc.detail
                else:
                    error_detail = str(exc.detail)

                raise

            except Exception as exc:
                status_code = 500
                error_detail = (
                    f"{type(exc).__name__}: {exc}"
                )[:1000]

                raise

            finally:
                duration_ms = int(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000
                )

                plugin_key = getattr(
                    request.state,
                    "plugin_audit_plugin_key",
                    None,
                )

                guild_id = getattr(
                    request.state,
                    "plugin_audit_guild_id",
                    None,
                )

                generation = getattr(
                    request.state,
                    "plugin_audit_generation",
                    None,
                )

                token_id = getattr(
                    request.state,
                    "plugin_audit_token_id",
                    None,
                )

                capability = getattr(
                    request.state,
                    "plugin_audit_capability",
                    None,
                )

                authenticated = bool(
                    getattr(
                        request.state,
                        "plugin_audit_authenticated",
                        False,
                    )
                )

                state_error = getattr(
                    request.state,
                    "plugin_audit_error",
                    None,
                )

                if state_error:
                    error_detail = str(state_error)

                allowed = (
                    authenticated
                    and status_code < 400
                )

                forwarded_for = request.headers.get(
                    "X-Forwarded-For",
                    "",
                )

                if forwarded_for:
                    client_ip = (
                        forwarded_for
                        .split(",", 1)[0]
                        .strip()
                    )
                elif request.client:
                    client_ip = request.client.host
                else:
                    client_ip = None

                await PluginApiAuditService.write(
                    PluginApiAuditEvent(
                        request_id=request_id,
                        plugin_key=plugin_key,
                        guild_id=guild_id,
                        generation=generation,
                        token_id=token_id,
                        capability=capability,
                        method=request.method,
                        path=request.url.path,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        authenticated=authenticated,
                        allowed=allowed,
                        client_ip=client_ip,
                        user_agent=request.headers.get(
                            "User-Agent"
                        ),
                        error_detail=error_detail,
                    )
                )

        return audited_handler
