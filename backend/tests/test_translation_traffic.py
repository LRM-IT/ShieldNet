import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock,MagicMock,patch
from app.api.routes.plugin_translator_groups import record_incoming,IncomingMessage


def test_incoming_is_scoped_and_deduplicated():
    async def check():
        item=SimpleNamespace(enabled=True,configuration={'groups':[{'enabled':True,'channels':[{'channel_id':'456'}]}]})
        result=MagicMock()
        result.scalar_one_or_none.side_effect=[789,None]
        session=SimpleNamespace(execute=AsyncMock(return_value=result),commit=AsyncMock())
        with patch('app.api.routes.plugin_translator_groups._installation',new=AsyncMock(return_value=item)):
            payload=IncomingMessage(channel_id=456,message_id=789)
            assert (await record_incoming(123,payload,session))['recorded']
            assert not (await record_incoming(123,payload,session))['recorded']
            query,params=session.execute.call_args.args
            assert 'ON CONFLICT(guild_id,message_id) DO NOTHING' in str(query)
            assert params=={'guild_id':123,'channel_id':456,'message_id':789}
            assert not (await record_incoming(123,IncomingMessage(channel_id=999,message_id=790),session))['recorded']
            item.enabled=False
            assert not (await record_incoming(123,payload,session))['recorded']
            assert session.execute.await_count==2
    asyncio.run(check())
