#!/usr/bin/env python3
"""Create a private initial Compose environment without printing secrets."""

from pathlib import Path
from secrets import token_urlsafe
import os


root = Path(__file__).resolve().parents[1]
template = (root / ".env.example").read_text(encoding="utf-8")
values = {
    "POSTGRES_PASSWORD": token_urlsafe(48),
    "SHIELDNET_SECRET_KEY": token_urlsafe(64),
    "SHIELDNET_INTERNAL_SERVICE_TOKEN": token_urlsafe(64),
    "PLUGIN_RUNTIME_TOKEN_SECRET": token_urlsafe(64),
}

for key, value in values.items():
    lines = template.splitlines()
    template = "\n".join(
        f"{key}={value}" if line.startswith(f"{key}=") else line
        for line in lines
    ) + "\n"

template = template.replace(
    "SHIELDNET_DISCORD_REDIRECT_URI=\n",
    "SHIELDNET_DISCORD_REDIRECT_URI=https://guildconsole.lrm-it.com/api/v1/auth/discord/callback\n",
)

target = root / ".env"
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.write(template)
print(f"Created {target} with mode 0600; Discord credentials and migration keys still need to be supplied.")
