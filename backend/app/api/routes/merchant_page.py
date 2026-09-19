from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.services.settings import SettingsService

router=APIRouter(tags=["Public merchant information"])
MODULE="merchant_public_page"
DEFAULTS={
 "business_name":"LRM-IT / GuildConsole","tax_id":"","legal_address":"","actual_address":"","phone":"","email":"",
 "service_description":"GuildConsole надає цифровий доступ до інструментів адміністрування Discord-серверів, автоматизації, безпеки та плагінів.",
 "service_terms":"Доступ активується в електронній формі для обраного Discord-сервера після успішної оплати. Фізична доставка не здійснюється. Період активації зазначається до підтвердження платежу.",
 "payment_methods":"Онлайн-оплата платіжними картками Visa та Mastercard через WayForPay. Валюта списання та остаточна сума відображаються до підтвердження платежу.",
 "service_area":"Цифрові послуги надаються онлайн. Доступність може залежати від обмежень Discord та сторонніх сервісів у країні клієнта.",
 "refund_policy":"Для повернення коштів зверніться до продавця за контактами на цій сторінці, вкажіть номер платежу та причину звернення. Заявка розглядається протягом 7 робочих днів. Кошти повертаються на початковий спосіб оплати у випадках, передбачених законом, або якщо оплачена послуга не була надана.",
 "cancellation_policy":"Скасування можна запросити до активації послуги. Після активації можливість скасування та повернення залежить від невикористаного періоду, причини звернення та вимог чинного законодавства.",
 "public_offer":"Оплата підтверджує, що клієнт ознайомився з описом послуги, ціною, строком активації, правилами повернення та цими умовами й приймає публічну пропозицію щодо надання обраної цифрової послуги.",
 "privacy_policy":"Персональні та пов’язані з оплатою дані обробляються лише для автентифікації клієнта, надання послуги, проведення платежу, запобігання шахрайству та обробки звернень. Дані платіжної картки обробляє платіжний провайдер; GuildConsole їх не зберігає.",
 "updated_label":""
}

class MerchantPageUpdate(BaseModel):
    business_name:str=Field(max_length=300);tax_id:str=Field(max_length=100);legal_address:str=Field(max_length=500);actual_address:str=Field(max_length=500);phone:str=Field(max_length=100);email:str=Field(max_length=320)
    service_description:str=Field(max_length=10000);service_terms:str=Field(max_length=10000);payment_methods:str=Field(max_length=5000);service_area:str=Field(max_length=5000);refund_policy:str=Field(max_length=10000);cancellation_policy:str=Field(max_length=10000);public_offer:str=Field(max_length=20000);privacy_policy:str=Field(max_length=20000)

async def content(session:AsyncSession):
    saved=await SettingsService(session).get(0,MODULE,"content",{})
    return {**DEFAULTS,**(saved if isinstance(saved,dict) else {})}

@router.get("/public/merchant-information")
async def public_merchant_information(session:AsyncSession=Depends(get_db_session)):
    return await content(session)

@router.put("/platform/merchant-information")
async def update_merchant_information(payload:MerchantPageUpdate,user:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    await SettingsService(session).set(guild_id=0,module=MODULE,key="content",value=payload.model_dump(),updated_by=user.id)
    return await content(session)
