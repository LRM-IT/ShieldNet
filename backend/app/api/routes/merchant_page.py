from fastapi import APIRouter, Depends, Query
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
SUPPORTED_LOCALES={"en","uk","ru","de","ar","fr","it","pl"}
LOCALIZED_DEFAULTS={
 "en":{"service_description":"GuildConsole provides digital access to Discord server administration, automation, security and plugin tools.","service_terms":"Access is activated electronically for the selected Discord server after successful payment. No physical delivery is provided. The activation period is displayed before payment confirmation.","payment_methods":"Online payment by Visa and Mastercard through the connected payment provider. The charge currency and final amount are displayed before confirmation.","service_area":"Digital services are provided online. Availability may depend on Discord and third-party service restrictions in the customer's country.","refund_policy":"To request a refund, contact the seller using the details on this page and provide the payment number and reason. Requests are reviewed within 7 business days. Funds are returned to the original payment method where required by law or when the paid service was not provided.","cancellation_policy":"Cancellation may be requested before service activation. After activation, eligibility depends on the unused period, the reason for the request and applicable law.","public_offer":"Payment confirms that the customer has reviewed the service description, price, activation period, refund rules and these terms, and accepts the public offer for the selected digital service.","privacy_policy":"We process personal data only for authentication, service delivery, payments, fraud prevention, support and legal obligations. Payment card data is handled by the payment provider and is not stored by GuildConsole. Necessary cookies and browser storage are used for sessions, security, language and interface preferences. Analytics starts only after consent. You may request access, correction or deletion using the contacts on this page."},
 "ru":{"service_description":"GuildConsole предоставляет цифровой доступ к инструментам администрирования Discord-серверов, автоматизации, безопасности и плагинам.","service_terms":"Доступ активируется в электронной форме для выбранного Discord-сервера после успешной оплаты. Физическая доставка не осуществляется. Период активации указывается до подтверждения платежа.","payment_methods":"Онлайн-оплата картами Visa и Mastercard через подключённого платёжного провайдера. Валюта списания и итоговая сумма отображаются до подтверждения.","service_area":"Цифровые услуги предоставляются онлайн. Доступность может зависеть от ограничений Discord и сторонних сервисов в стране клиента.","refund_policy":"Для возврата средств свяжитесь с продавцом по контактам на этой странице, укажите номер платежа и причину обращения. Заявка рассматривается в течение 7 рабочих дней. Средства возвращаются исходным способом оплаты в предусмотренных законом случаях или если оплаченная услуга не была предоставлена.","cancellation_policy":"Отмену можно запросить до активации услуги. После активации возможность отмены и возврата зависит от неиспользованного периода, причины обращения и требований законодательства.","public_offer":"Оплата подтверждает, что клиент ознакомился с описанием услуги, ценой, сроком активации, правилами возврата и настоящими условиями и принимает публичную оферту на выбранную цифровую услугу.","privacy_policy":"Мы обрабатываем персональные данные только для авторизации, предоставления услуг, проведения платежей, предотвращения мошенничества, поддержки и выполнения требований закона. Данные банковских карт обрабатывает платёжный провайдер; GuildConsole их не хранит. Необходимые cookie и хранилище браузера используются для сессии, безопасности, языка и настроек интерфейса. Аналитика запускается только после согласия. Запросить доступ, исправление или удаление данных можно по контактам на этой странице."}
}

class MerchantPageUpdate(BaseModel):
    business_name:str=Field(max_length=300);tax_id:str=Field(max_length=100);legal_address:str=Field(max_length=500);actual_address:str=Field(max_length=500);phone:str=Field(max_length=100);email:str=Field(max_length=320)
    service_description:str=Field(max_length=10000);service_terms:str=Field(max_length=10000);payment_methods:str=Field(max_length=5000);service_area:str=Field(max_length=5000);refund_policy:str=Field(max_length=10000);cancellation_policy:str=Field(max_length=10000);public_offer:str=Field(max_length=20000);privacy_policy:str=Field(max_length=20000)

async def content(session:AsyncSession,locale:str):
    locale=locale if locale in SUPPORTED_LOCALES else "en"
    service=SettingsService(session)
    legacy=await service.get(0,MODULE,"content",{})
    saved=await service.get(0,MODULE,f"content.{locale}",{})
    localized=LOCALIZED_DEFAULTS.get(locale,LOCALIZED_DEFAULTS["en"])
    legacy_values=legacy if isinstance(legacy,dict) and locale=="uk" else {}
    return {**DEFAULTS,**localized,**legacy_values,**(saved if isinstance(saved,dict) else {}),"locale":locale}

@router.get("/public/privacy-policy")
@router.get("/public/merchant-information",deprecated=True)
async def public_merchant_information(locale:str=Query("en"),session:AsyncSession=Depends(get_db_session)):
    return await content(session,locale)

@router.put("/platform/privacy-policy")
@router.put("/platform/merchant-information",deprecated=True)
async def update_merchant_information(payload:MerchantPageUpdate,locale:str=Query("en"),user:User=Depends(require_superadmin),session:AsyncSession=Depends(get_db_session)):
    locale=locale if locale in SUPPORTED_LOCALES else "en"
    await SettingsService(session).set(guild_id=0,module=MODULE,key=f"content.{locale}",value=payload.model_dump(),updated_by=user.id)
    return await content(session,locale)
