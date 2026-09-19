import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.plugin_control_service import PluginControlService

EMAIL_VAULT_KEY = "platform_email"


class EmailDeliveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.vault = PluginControlService(session)

    async def config(self) -> dict:
        names = ("enabled", "host", "port", "username", "password", "from_email", "from_name", "use_tls", "use_ssl")
        values = {name: (await self.vault.get_secret(EMAIL_VAULT_KEY, name) or "") for name in names}
        return {
            "enabled": values["enabled"] == "true", "host": values["host"],
            "port": int(values["port"] or 587), "username": values["username"],
            "password": values["password"], "from_email": values["from_email"],
            "from_name": values["from_name"] or "GuildConsole",
            "use_tls": values["use_tls"] != "false", "use_ssl": values["use_ssl"] == "true",
        }

    async def public_config(self) -> dict:
        cfg = await self.config()
        return {**{key: value for key, value in cfg.items() if key != "password"}, "password_saved": bool(cfg["password"]), "configured": bool(cfg["host"] and cfg["from_email"])}

    async def send(self, recipient: str, subject: str, body: str) -> None:
        cfg = await self.config()
        if not cfg["enabled"] or not cfg["host"] or not cfg["from_email"]:
            raise RuntimeError("SMTP is disabled or not configured")
        message = EmailMessage(); message["Subject"] = subject; message["From"] = f'{cfg["from_name"]} <{cfg["from_email"]}>'; message["To"] = recipient; message.set_content(body)
        def deliver():
            if cfg["use_ssl"]:
                client = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20, context=ssl.create_default_context())
            else:
                client = smtplib.SMTP(cfg["host"], cfg["port"], timeout=20)
            try:
                if cfg["use_tls"] and not cfg["use_ssl"]: client.starttls(context=ssl.create_default_context())
                if cfg["username"]: client.login(cfg["username"], cfg["password"])
                client.send_message(message)
            finally: client.quit()
        await asyncio.to_thread(deliver)
