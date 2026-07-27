from __future__ import annotations

import re
import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from app.plugin_worker.migration_preflight import PluginMigrationPreflight
from app.plugin_worker.migrations import PluginMigration


class PluginMigrationExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationExecutionItem:
    order: int
    filename: str
    checksum_sha256: str
    status: str
    execution_time_ms: int
    statement_count: int
    error: str | None = None


@dataclass(frozen=True)
class MigrationDryRunResult:
    plugin_key: str
    schema_name: str
    status: str
    rolled_back: bool
    migrations: tuple[MigrationExecutionItem, ...]

    @property
    def total_execution_time_ms(self) -> int:
        return sum(item.execution_time_ms for item in self.migrations)


def quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", identifier):
        raise PluginMigrationExecutionError(
            f"Unsafe PostgreSQL identifier: {identifier}"
        )
    return f'"{identifier}"'


def split_sql_statements(sql: str) -> tuple[str, ...]:
    statements, buffer = [], []
    i, n = 0, len(sql)
    single = double = line_comment = False
    block_depth = 0
    dollar_tag = None

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if line_comment:
            buffer.append(ch)
            if ch == "\n":
                line_comment = False
            i += 1
            continue

        if block_depth:
            buffer.append(ch)
            if ch == "/" and nxt == "*":
                buffer.append(nxt)
                block_depth += 1
                i += 2
                continue
            if ch == "*" and nxt == "/":
                buffer.append(nxt)
                block_depth -= 1
                i += 2
                continue
            i += 1
            continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buffer.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buffer.append(ch)
                i += 1
            continue

        if single:
            buffer.append(ch)
            if ch == "'" and nxt == "'":
                buffer.append(nxt)
                i += 2
                continue
            if ch == "'":
                single = False
            i += 1
            continue

        if double:
            buffer.append(ch)
            if ch == '"' and nxt == '"':
                buffer.append(nxt)
                i += 2
                continue
            if ch == '"':
                double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            buffer.extend((ch, nxt))
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            buffer.extend((ch, nxt))
            block_depth = 1
            i += 2
            continue
        if ch == "'":
            buffer.append(ch)
            single = True
            i += 1
            continue
        if ch == '"':
            buffer.append(ch)
            double = True
            i += 1
            continue
        if ch == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[i:])
            if match:
                dollar_tag = match.group(0)
                buffer.append(dollar_tag)
                i += len(dollar_tag)
                continue
        if ch == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer.clear()
            i += 1
            continue

        buffer.append(ch)
        i += 1

    if single or double or dollar_tag is not None or block_depth:
        raise PluginMigrationExecutionError(
            "SQL contains an unterminated quote or comment"
        )

    trailing = "".join(buffer).strip()
    if trailing:
        statements.append(trailing)
    return tuple(statements)


class PluginMigrationDryRunner:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        statement_timeout_ms: int = 30000,
        lock_timeout_ms: int = 5000,
    ) -> None:
        self.engine = engine
        self.statement_timeout_ms = statement_timeout_ms
        self.lock_timeout_ms = lock_timeout_ms

    async def run(
        self,
        preflight: PluginMigrationPreflight,
    ) -> MigrationDryRunResult:
        schema = quote_identifier(preflight.schema_name)
        results = []

        async with self.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.exec_driver_sql(
                    f"SET LOCAL statement_timeout = "
                    f"'{self.statement_timeout_ms}ms'"
                )
                await connection.exec_driver_sql(
                    f"SET LOCAL lock_timeout = "
                    f"'{self.lock_timeout_ms}ms'"
                )
                await connection.exec_driver_sql(
                    f"CREATE SCHEMA IF NOT EXISTS {schema}"
                )
                await connection.exec_driver_sql(
                    f"SET LOCAL search_path TO {schema}, public"
                )

                for migration in preflight.pending:
                    results.append(
                        await self._execute_migration(
                            connection,
                            migration,
                        )
                    )
            except Exception as exc:
                await transaction.rollback()
                if isinstance(exc, PluginMigrationExecutionError):
                    raise
                raise PluginMigrationExecutionError(str(exc)) from exc
            else:
                await transaction.rollback()

        return MigrationDryRunResult(
            plugin_key=preflight.plugin_key,
            schema_name=preflight.schema_name,
            status="ok",
            rolled_back=True,
            migrations=tuple(results),
        )

    async def _execute_migration(
        self,
        connection,
        migration: PluginMigration,
    ) -> MigrationExecutionItem:
        statements = split_sql_statements(
            migration.path.read_text(encoding="utf-8")
        )
        started = time.perf_counter()
        try:
            for statement in statements:
                await connection.exec_driver_sql(statement)
        except Exception as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            raise PluginMigrationExecutionError(
                f"{migration.filename} failed after "
                f"{elapsed} ms: {exc}"
            ) from exc

        elapsed = int((time.perf_counter() - started) * 1000)
        return MigrationExecutionItem(
            order=migration.order,
            filename=migration.filename,
            checksum_sha256=migration.checksum_sha256,
            status="ok",
            execution_time_ms=elapsed,
            statement_count=len(statements),
        )
