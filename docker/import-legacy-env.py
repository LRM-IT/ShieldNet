#!/usr/bin/env python3
"""Import only deployment credentials needed from a ShieldNet backup."""

from pathlib import Path
import os


root = Path(__file__).resolve().parents[1]
source = Path('/root/shieldnet-migration-20260914/extracted/etc/shieldnet')
target = root / '.env'

required = {
    'SHIELDNET_DISCORD_CLIENT_ID',
    'SHIELDNET_DISCORD_CLIENT_SECRET',
    'SHIELDNET_DISCORD_BOT_TOKEN',
    'SHIELDNET_DISCORD_APPLICATION_ID',
    'AI_CREDENTIALS_MASTER_KEY',
    'SHIELDNET_PLUGIN_VAULT_KEY',
}
optional = {
    'SHIELDNET_SUPERADMIN_IDS',
    'SHIELDNET_DEFAULT_LANGUAGE',
    'SHIELDNET_TIMEZONE',
    'SHIELDNET_DISCORD_OAUTH_SCOPES',
    'SHIELDNET_WORKER_QUEUE',
    'SHIELDNET_DISCORD_JOB_QUEUE',
    'SHIELDNET_SYNC_COMMANDS_ON_START',
    'SHIELDNET_PLUGIN_ALLOWED_PERMISSIONS',
}
allowed = required | optional

imported: dict[str, str] = {}
for relative in ('backend/backend.env', 'backend/discord.env', 'bot/bot.env',
                 'scheduler/scheduler.env', 'plugin-worker.env'):
    for line in (source / relative).read_text(encoding='utf-8').splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key in allowed and value.strip():
            imported[key] = value

missing = required - imported.keys()
if missing:
    raise SystemExit('Missing required credentials: ' + ', '.join(sorted(missing)))

lines = target.read_text(encoding='utf-8').splitlines()
seen: set[str] = set()
for index, line in enumerate(lines):
    key = line.split('=', 1)[0]
    if key in imported:
        lines[index] = f'{key}={imported[key]}'
        seen.add(key)
for key in sorted(imported.keys() - seen):
    lines.append(f'{key}={imported[key]}')

temporary = target.with_name('.env.tmp')
fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as stream:
    stream.write('\n'.join(lines) + '\n')
temporary.replace(target)
print('Imported legacy credentials into private .env; no values printed.')
