from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.plugin_worker.migrations import PluginMigration


class PluginMigrationPolicyError(ValueError):
    """Raised when migration SQL violates ShieldNet plugin policy."""


@dataclass(frozen=True)
class MigrationPolicyViolation:
    filename: str
    rule: str
    line: int
    excerpt: str


_FORBIDDEN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "transaction-control",
        re.compile(
            r"(?im)^\s*(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE\s+SAVEPOINT)\b"
        ),
    ),
    (
        "role-management",
        re.compile(
            r"(?im)^\s*(SET\s+ROLE|RESET\s+ROLE|CREATE\s+ROLE|ALTER\s+ROLE|"
            r"DROP\s+ROLE|GRANT\s+.+\s+TO\s+.+|REVOKE\s+.+\s+FROM\s+.+)\b"
        ),
    ),
    (
        "database-management",
        re.compile(
            r"(?im)^\s*(CREATE|ALTER|DROP)\s+DATABASE\b"
        ),
    ),
    (
        "tablespace-management",
        re.compile(
            r"(?im)^\s*(CREATE|ALTER|DROP)\s+TABLESPACE\b"
        ),
    ),
    (
        "extension-management",
        re.compile(
            r"(?im)^\s*(CREATE|ALTER|DROP)\s+EXTENSION\b"
        ),
    ),
    (
        "system-schema-access",
        re.compile(
            r"(?i)\b(pg_catalog|information_schema|pg_toast)\s*\."
        ),
    ),
    (
        "copy-program",
        re.compile(
            r"(?is)\bCOPY\b.+\bPROGRAM\b"
        ),
    ),
    (
        "large-object-server-files",
        re.compile(
            r"(?i)\b(pg_read_file|pg_write_file|pg_ls_dir|lo_import|lo_export)\s*\("
        ),
    ),
    (
        "session-authorization",
        re.compile(
            r"(?im)^\s*SET\s+SESSION\s+AUTHORIZATION\b"
        ),
    ),
    (
        "untrusted-language",
        re.compile(
            r"(?i)\bLANGUAGE\s+(plpythonu|plperlu|plsh|c)\b"
        ),
    ),
)


def strip_sql_comments(sql: str) -> str:
    """
    Remove SQL comments while preserving line count.

    This is intentionally conservative and is not a full SQL parser.
    """
    def block_replacement(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    without_blocks = re.sub(
        r"/\*.*?\*/",
        block_replacement,
        sql,
        flags=re.DOTALL,
    )

    lines: list[str] = []
    for line in without_blocks.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        body = re.sub(r"--.*$", "", body)
        lines.append(body + newline)

    return "".join(lines)


def validate_migration_sql(
    migration: PluginMigration,
) -> tuple[MigrationPolicyViolation, ...]:
    sql = migration.path.read_text(encoding="utf-8")
    inspected = strip_sql_comments(sql)
    violations: list[MigrationPolicyViolation] = []

    for rule, pattern in _FORBIDDEN_RULES:
        for match in pattern.finditer(inspected):
            line = inspected.count("\n", 0, match.start()) + 1
            source_line = sql.splitlines()[line - 1] if sql.splitlines() else ""
            violations.append(
                MigrationPolicyViolation(
                    filename=migration.filename,
                    rule=rule,
                    line=line,
                    excerpt=source_line.strip()[:240],
                )
            )

    return tuple(violations)


def validate_migration_policy(
    migrations: Iterable[PluginMigration],
) -> None:
    violations: list[MigrationPolicyViolation] = []

    for migration in migrations:
        violations.extend(validate_migration_sql(migration))

    if not violations:
        return

    details = "; ".join(
        f"{item.filename}:{item.line} [{item.rule}] {item.excerpt}"
        for item in violations
    )
    raise PluginMigrationPolicyError(
        "Plugin migration policy rejected SQL: " + details
    )


def required_schema_prefix(plugin_key: str) -> str:
    normalized = plugin_key.strip().lower().replace("-", "_")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]{1,95}", normalized):
        raise PluginMigrationPolicyError("Invalid plugin key for schema mapping")
    return f"plugin_{normalized}"


def validate_schema_scope(
    migrations: Iterable[PluginMigration],
    *,
    plugin_key: str,
) -> None:
    """
    Ensure explicitly qualified CREATE/ALTER/DROP targets stay in plugin schema.

    Unqualified object names remain allowed because the future runner will set
    a plugin-specific search_path.
    """
    allowed_schema = required_schema_prefix(plugin_key)

    qualified_target = re.compile(
        r"""(?ix)
        \b(?:CREATE|ALTER|DROP)\s+
        (?:TABLE|INDEX|SEQUENCE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|TYPE)\s+
        (?:IF\s+(?:NOT\s+)?EXISTS\s+)?
        ["']?(?P<schema>[a-z_][a-z0-9_]*)["']?\s*\.
        """
    )

    violations: list[str] = []

    for migration in migrations:
        sql = strip_sql_comments(
            migration.path.read_text(encoding="utf-8")
        )
        for match in qualified_target.finditer(sql):
            schema = match.group("schema").lower()
            if schema != allowed_schema:
                line = sql.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{migration.filename}:{line} targets schema {schema}, "
                    f"expected {allowed_schema}"
                )

    if violations:
        raise PluginMigrationPolicyError(
            "Plugin migration escaped its schema: " + "; ".join(violations)
        )
