from app.plugins.base import BackendPlugin

class WizardPlugin(BackendPlugin):
    def router(self): return None
    async def startup(self): return None
    async def shutdown(self): return None

async def setup(context): return None
async def start(context): return None
async def stop(context): return None
async def health(context): return {"status":"ready","plugin_key":"wizard","guild_id":getattr(context,"guild_id",None)}
