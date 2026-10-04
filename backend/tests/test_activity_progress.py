from app.api.routes.plugin_activity_ranking import level_progress


def test_messages_remaining_follow_level_curve_and_message_xp():
    settings={'level_base_points':100,'level_growth':1.5,'message_points':3}
    assert level_progress(0,settings)['messages_to_next_level']==34
    assert level_progress(99.9,settings)['messages_to_next_level']==1
    result=level_progress(100,settings)
    assert result['next_level']==3
    assert result['messages_to_next_level']==61
    assert level_progress(200,settings)['messages_to_next_level']==28
    assert level_progress(200,{**settings,'message_points':0})['messages_to_next_level'] is None
