import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from PIL import Image
from bot.level_card import render_level_card
from bot.plugin_activity_ranking import ActivityRanking


def test_cards_render_with_and_without_roles():
    avatar=BytesIO()
    Image.new('RGB',(64,64),'red').save(avatar,format='PNG')
    for roles in ([],['Chat Enjoyer'],['A very long reward role name that should wrap correctly', 'Second role']):
        data=render_level_card(avatar.getvalue(),'Test member',4,roles)
        assert Image.open(BytesIO(data)).size==(1200,400)
        assert len(data)<8_000_000
    assert render_level_card(b'bad image','Test',120,[])
    custom=render_level_card(None,'Test',4,[],avatar.getvalue())
    assert Image.open(BytesIO(custom)).size==(1200,400)
    assert custom != render_level_card(None,'Test',4,[])


def test_rewards_only_show_after_success_and_all_destinations_get_fresh_files():
    async def check(fail):
        role=SimpleNamespace(id=1,name='Chat Enjoyer',mention='<@&1>')
        avatar=SimpleNamespace(read=AsyncMock(return_value=b'avatar'))
        avatar.with_size=lambda _:avatar
        avatar.with_static_format=lambda _:avatar
        channel=SimpleNamespace(send=AsyncMock())
        member=SimpleNamespace(id=3,roles=[],display_name='Test',mention='<@3>',display_avatar=avatar,
            guild=SimpleNamespace(id=2,get_role=lambda _:role,get_channel=lambda _:channel),
            add_roles=AsyncMock(side_effect=RuntimeError('Forbidden') if fail else None),send=AsyncMock())
        source=SimpleNamespace(reply=AsyncMock())
        result={'recorded':True,'reward_role_ids':['1'],'score':{'level':4,'points':300},'leveled_up':True,
            'announce_level_up':True,'announce_in_reply':True,'announce_in_dm':True,'announce_in_channel':True,'announcement_channel_id':'9'}
        with patch('bot.plugin_activity_ranking.render_level_card',return_value=b'png') as render:
            await ActivityRanking(None).apply_rewards(member,result,source)
            assert render.call_args.args[3]==([] if fail else ['Chat Enjoyer'])
        files=[send.call_args.kwargs['file'] for send in (source.reply,member.send,channel.send)]
        assert len({id(f) for f in files})==3
        assert all(f.filename=='level-up.png' for f in files)
        for f in files:f.close()
        embed=member.send.call_args.kwargs['embed']
        assert embed.image.url=='attachment://level-up.png'
        assert bool(embed.fields)==(not fail)
    asyncio.run(check(False))
    asyncio.run(check(True))
