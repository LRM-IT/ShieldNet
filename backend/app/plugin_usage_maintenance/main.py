from __future__ import annotations

import asyncio
import logging

from app.services.plugin_usage_aggregation_service import (
    plugin_usage_aggregation_service,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)s "
        "%(name)s %(message)s"
    ),
)


async def async_main() -> None:
    result = (
        await plugin_usage_aggregation_service
        .run_daily()
    )

    print(
        "Plugin usage maintenance completed:",
        result,
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
