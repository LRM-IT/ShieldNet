import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import discord
from bot.plugin_idea_collection import language_for, SurveyButton, IdeaModal, private_view, IdeaCollectionWorker, ui_text, UI_TEXT


def survey():
    text = {"title":"Ideas", "description":"Tell us", "button":"Answer now", "label":"Your idea", "placeholder":"Describe it", "thanks":"Thank you"}
    return {"id":"12345678-1234-1234-1234-123456789012", "guild_id":"123", "primary_language":"en", "translations":{"en":text,"ru":{**text,"button":"Ответить сейчас"},"uk":text}}


def test_language_resolution():
    data=survey()
    groups=[{"enabled":True,"language_roles":{"ru":"10","uk":"20"}}]
    assert language_for(data,{"10"},groups,"en-US")=="ru"
    assert language_for(data,{"10","20"},groups,"uk")=="uk"
    assert language_for(data,set(),groups,"en-US")=="en"
    assert language_for(data,set(),groups,"fr")=="en"
    assert language_for(data,{"10"},[{**groups[0],"enabled":False}],"en-US")=="en"


def test_persistent_button_and_private_form():
    async def run():
        data=survey()
        button=SurveyButton(data['id'])
        assert button.item.custom_id=="gc_idea:"+data['id']
        view=private_view(None,data,'ru')
        assert view.children[-1].label=='Ответить сейчас'
        assert view.children[0].placeholder=='🌐 Выберите язык'
        for code in ['en','ru','uk','de','fr','it','pl','ar']:
            assert ui_text(code, 'language') and ui_text(code, 'unavailable')
        assert ui_text('fr-FR','language')==UI_TEXT['fr']['language']
        worker=SimpleNamespace(request=AsyncMock())
        modal=IdeaModal(worker,data,'ru',77)
        modal.idea._value='A suggestion'
        interaction=SimpleNamespace(user=SimpleNamespace(id=77,display_name='Server nickname'),guild_id=123,
                                    response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
        await modal.on_submit(interaction)
        payload=worker.request.call_args.args[-1]
        assert payload['text']=='A suggestion' and payload['display_name']=='Server nickname'
        assert payload['language']=='ru'
        assert interaction.followup.send.call_args.kwargs['ephemeral'] is True
    asyncio.run(run())


def test_publication_edits_and_closes_existing_message():
    async def run():
        data={**survey(), 'channel_id':'456', 'message_id':'789', 'active':True}
        channel=MagicMock(spec=discord.TextChannel)
        channel.guild=SimpleNamespace(id=123)
        message=SimpleNamespace(id=789,edit=AsyncMock())
        channel.fetch_message=AsyncMock(return_value=message)
        channel.send=AsyncMock()
        guild=SimpleNamespace(id=123,get_channel_or_thread=lambda _:channel)
        worker=IdeaCollectionWorker(SimpleNamespace())
        worker.request=AsyncMock()
        await worker.process(guild,{'item':data,'claim_id':'lease'})
        channel.send.assert_not_called()
        assert message.edit.call_args.kwargs['view'] is not None
        assert worker.request.call_args.args[-1]['message_id']==789
        data['active']=False
        await worker.process(guild,{'item':data,'claim_id':'lease'})
        assert message.edit.call_args.kwargs['view'] is None
        channel.send.assert_not_called()
    asyncio.run(run())


def test_recovers_publication_by_hidden_button_id():
    async def run():
        data={**survey(), 'channel_id':'456', 'message_id':None, 'active':True}
        channel=MagicMock(spec=discord.TextChannel)
        channel.guild=SimpleNamespace(id=123)
        message=SimpleNamespace(id=789,edit=AsyncMock(),author=SimpleNamespace(id=99),embeds=[],
            components=[SimpleNamespace(children=[SimpleNamespace(custom_id='gc_idea:'+data['id'])])])
        async def history(**kwargs):
            yield message
        channel.history=history
        channel.send=AsyncMock()
        guild=SimpleNamespace(id=123,get_channel_or_thread=lambda _:channel)
        worker=IdeaCollectionWorker(SimpleNamespace(user=SimpleNamespace(id=99)))
        worker.request=AsyncMock()
        await worker.process(guild,{'item':data,'claim_id':'lease'})
        channel.send.assert_not_called()
        message.edit.assert_awaited_once()
        assert message.edit.call_args.kwargs['embed'].footer.text=='GuildConsole'
        assert worker.request.call_args.args[-1]['message_id']==789
    asyncio.run(run())


def test_public_language_menu_and_private_translation():
    from bot.plugin_idea_collection import public_view, SurveyLanguageSelect
    async def run():
        data={**survey(), 'message_id':'789', 'language_labels':{
            'en':{'name':'English','flag':'\U0001f1ec\U0001f1e7'},
            'ru':{'name':'Russian','flag':'\U0001f1f7\U0001f1fa'}}}
        view=public_view(data)
        assert view.is_persistent()
        select=view.children[0]
        assert isinstance(select, SurveyLanguageSelect)
        assert select.item.options[0].label=='English'
        assert str(select.item.options[0].emoji)=='\U0001f1ec\U0001f1e7'
        assert select.item.options[1].label=='Russian'
        guild=SimpleNamespace(id=123)
        worker=SimpleNamespace(request=AsyncMock(return_value=data))
        interaction=SimpleNamespace(data={'values':['ru']}, guild=guild, guild_id=123,
            message=SimpleNamespace(id=789),locale='en-US',user=SimpleNamespace(roles=[]),
            client=SimpleNamespace(idea_collection=worker,managed_guilds=[guild],
                language_selection=SimpleNamespace(configuration=AsyncMock(return_value={}))),
            response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
        restored=await SurveyLanguageSelect.from_custom_id(interaction,select.item,{'survey':data['id']})
        await restored.callback(interaction)
        sent=interaction.followup.send.call_args.kwargs
        assert sent['ephemeral'] is True
        assert sent['view'].children[-1].language=='ru'
        assert sent['view'].children[0].options[0].label=='English'
    asyncio.run(run())
