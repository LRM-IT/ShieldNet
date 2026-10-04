from io import BytesIO
from PIL import Image
from fastapi import HTTPException
from app.api.routes.plugin_activity_ranking import normalize_background, config
from types import SimpleNamespace


def test_background_normalizes_and_preserves_configuration():
    raw=BytesIO()
    Image.new('RGB',(800,800),'blue').save(raw,'PNG')
    image=Image.open(BytesIO(normalize_background(raw.getvalue())))
    assert image.size==(1200,400)
    assert image.format=='JPEG'
    assert config(SimpleNamespace(configuration={'background_id':'test'}))['background_id']=='test'
    for content in (b'not an image',b'<svg></svg>'):
        try:normalize_background(content)
        except HTTPException as exc:assert exc.status_code==422
        else:raise AssertionError('Invalid image accepted')
