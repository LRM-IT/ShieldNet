from __future__ import annotations

import io
import logging
import httpx

log = logging.getLogger(__name__)


async def fetch_template_result_image(worker, poll: dict) -> io.BytesIO | None:
    if not poll.get("publish_result_image", True):
        return None

    poll_id = poll.get("id")
    if not poll_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.get(
                f"{worker.base}/api/v1/internal/discord/plugins/voting/{poll_id}/result-image",
                headers=worker.headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            output = io.BytesIO(response.content)
            output.seek(0)
            return output
    except Exception:
        log.exception("Unable to render voting result through Template Bank")
        return None
