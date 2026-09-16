"""Build GuildConsole UI locale catalogues from the canonical English schema.

Every locale contains the complete key tree. New keys are therefore added to
English first and inherited safely until a native translation is supplied.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "admin-frontend" / "public" / "locales"

LANGUAGES = {
    "de": ("🇩🇪", "Deutsch", "German", ["de", "de-DE", "de-AT", "de-CH"], False),
    "ar": ("🇸🇦", "العربية", "Arabic", ["ar", "ar-SA", "ar-AE", "ar-EG"], True),
    "fr": ("🇫🇷", "Français", "French", ["fr", "fr-FR", "fr-CA"], False),
    "it": ("🇮🇹", "Italiano", "Italian", ["it", "it-IT"], False),
    "pl": ("🇵🇱", "Polski", "Polish", ["pl", "pl-PL"], False),
}

TRANSLATIONS = {
    "de": {
        "CONTROL FABRIC":"STEUERZENTRALE","CONTROL PLANE":"STEUERUNGSEBENE","Encrypted session active":"Verschlüsselte Sitzung aktiv","Workspace":"Arbeitsbereich","Servers":"Server","Plugin fabric":"Plugin-Plattform","Jobs center":"Auftragszentrum","Operations":"Betrieb","Core server":"Kernserver","Installed plugins":"Installierte Plugins","Overview":"Übersicht","Members":"Mitglieder","Security":"Sicherheit","Plugin runtime":"Plugin-Laufzeit","Audit trail":"Prüfprotokoll","Server control":"Serversteuerung","SYSTEM NOMINAL":"SYSTEM NORMAL","SECURE CONSOLE":"GESICHERTE KONSOLE","Profile":"Profil","Sign out":"Abmelden","Language and region":"Sprache und Region","Interface language":"Oberflächensprache","Timezone":"Zeitzone","Save":"Speichern","Cancel":"Abbrechen","Delete":"Löschen","Settings":"Einstellungen","Enable":"Aktivieren","Disable":"Deaktivieren","Start":"Starten","Stop":"Stoppen","Add":"Hinzufügen","Create":"Erstellen","Refresh":"Aktualisieren","Search":"Suchen","Loading…":"Wird geladen…","Completed":"Abgeschlossen","Operation failed":"Vorgang fehlgeschlagen",
    },
    "ar": {
        "CONTROL FABRIC":"نسيج التحكم","CONTROL PLANE":"مستوى التحكم","Encrypted session active":"الجلسة المشفرة نشطة","Workspace":"مساحة العمل","Servers":"الخوادم","Plugin fabric":"منصة الإضافات","Jobs center":"مركز المهام","Operations":"العمليات","Core server":"الخادم الأساسي","Installed plugins":"الإضافات المثبتة","Overview":"نظرة عامة","Members":"الأعضاء","Security":"الأمان","Plugin runtime":"تشغيل الإضافات","Audit trail":"سجل التدقيق","Server control":"إدارة الخادم","SYSTEM NOMINAL":"النظام يعمل","SECURE CONSOLE":"وحدة تحكم آمنة","Profile":"الملف الشخصي","Sign out":"تسجيل الخروج","Language and region":"اللغة والمنطقة","Interface language":"لغة الواجهة","Timezone":"المنطقة الزمنية","Save":"حفظ","Cancel":"إلغاء","Delete":"حذف","Settings":"الإعدادات","Enable":"تمكين","Disable":"تعطيل","Start":"بدء","Stop":"إيقاف","Add":"إضافة","Create":"إنشاء","Refresh":"تحديث","Search":"بحث","Loading…":"جارٍ التحميل…","Completed":"اكتمل","Operation failed":"فشلت العملية",
    },
    "fr": {
        "CONTROL FABRIC":"CENTRE DE CONTRÔLE","CONTROL PLANE":"PLAN DE CONTRÔLE","Encrypted session active":"Session chiffrée active","Workspace":"Espace de travail","Servers":"Serveurs","Plugin fabric":"Plateforme des plugins","Jobs center":"Centre des tâches","Operations":"Opérations","Core server":"Serveur principal","Installed plugins":"Plugins installés","Overview":"Vue d’ensemble","Members":"Membres","Security":"Sécurité","Plugin runtime":"Exécution des plugins","Audit trail":"Journal d’audit","Server control":"Gestion du serveur","SYSTEM NOMINAL":"SYSTÈME OPÉRATIONNEL","SECURE CONSOLE":"CONSOLE SÉCURISÉE","Profile":"Profil","Sign out":"Se déconnecter","Language and region":"Langue et région","Interface language":"Langue de l’interface","Timezone":"Fuseau horaire","Save":"Enregistrer","Cancel":"Annuler","Delete":"Supprimer","Settings":"Paramètres","Enable":"Activer","Disable":"Désactiver","Start":"Démarrer","Stop":"Arrêter","Add":"Ajouter","Create":"Créer","Refresh":"Actualiser","Search":"Rechercher","Loading…":"Chargement…","Completed":"Terminé","Operation failed":"Échec de l’opération",
    },
    "it": {
        "CONTROL FABRIC":"CENTRO DI CONTROLLO","CONTROL PLANE":"PIANO DI CONTROLLO","Encrypted session active":"Sessione crittografata attiva","Workspace":"Area di lavoro","Servers":"Server","Plugin fabric":"Piattaforma plugin","Jobs center":"Centro attività","Operations":"Operazioni","Core server":"Server principale","Installed plugins":"Plugin installati","Overview":"Panoramica","Members":"Membri","Security":"Sicurezza","Plugin runtime":"Esecuzione plugin","Audit trail":"Registro di controllo","Server control":"Gestione server","SYSTEM NOMINAL":"SISTEMA OPERATIVO","SECURE CONSOLE":"CONSOLE SICURA","Profile":"Profilo","Sign out":"Esci","Language and region":"Lingua e regione","Interface language":"Lingua dell’interfaccia","Timezone":"Fuso orario","Save":"Salva","Cancel":"Annulla","Delete":"Elimina","Settings":"Impostazioni","Enable":"Abilita","Disable":"Disabilita","Start":"Avvia","Stop":"Arresta","Add":"Aggiungi","Create":"Crea","Refresh":"Aggiorna","Search":"Cerca","Loading…":"Caricamento…","Completed":"Completato","Operation failed":"Operazione non riuscita",
    },
    "pl": {
        "CONTROL FABRIC":"CENTRUM STEROWANIA","CONTROL PLANE":"WARSTWA STEROWANIA","Encrypted session active":"Szyfrowana sesja jest aktywna","Workspace":"Obszar roboczy","Servers":"Serwery","Plugin fabric":"Platforma wtyczek","Jobs center":"Centrum zadań","Operations":"Operacje","Core server":"Serwer główny","Installed plugins":"Zainstalowane wtyczki","Overview":"Przegląd","Members":"Członkowie","Security":"Bezpieczeństwo","Plugin runtime":"Środowisko wtyczek","Audit trail":"Dziennik audytu","Server control":"Zarządzanie serwerem","SYSTEM NOMINAL":"SYSTEM DZIAŁA","SECURE CONSOLE":"BEZPIECZNA KONSOLA","Profile":"Profil","Sign out":"Wyloguj","Language and region":"Język i region","Interface language":"Język interfejsu","Timezone":"Strefa czasowa","Save":"Zapisz","Cancel":"Anuluj","Delete":"Usuń","Settings":"Ustawienia","Enable":"Włącz","Disable":"Wyłącz","Start":"Uruchom","Stop":"Zatrzymaj","Add":"Dodaj","Create":"Utwórz","Refresh":"Odśwież","Search":"Szukaj","Loading…":"Ładowanie…","Completed":"Zakończono","Operation failed":"Operacja nie powiodła się",
    },
}

PLUGIN_NAMES = {
    "uk": ["Вітання","Антифлуд","Голосування","Верифікація","Керівництво","Модерація","Перекладач","Автоматизації","Меню ролей","AI Автомодерація","Менеджер подій","Планувальник війни","Активність і рейтинг","Аудит і безпека","Резервні копії","Мережа серверів","Звернення","Журналювання","Особисті повідомлення","Вибір мови","Групи перекладу"],
    "ru": ["Приветствие","Антифлуд","Голосования","Верификация","Руководство","Модерация","Переводчик","Автоматизации","Меню ролей","AI Автомодерация","Менеджер событий","Планировщик войны","Активность и рейтинг","Аудит и безопасность","Резервные копии","Сеть серверов","Обращения","Журналирование","Личные сообщения","Выбор языка","Группы перевода"],
    "de": ["Willkommen","AntiFlood","Abstimmungen","Verifizierung","Leitung","Moderation","Übersetzer","Automatisierungen","Rollenmenü","KI AutoMod","Ereignismanager","Kriegsplaner","Aktivität & Rangliste","Audit & Sicherheit","Sicherung & Wiederherstellung","Serverübergreifendes Netzwerk","Tickets","Protokollierung","Direktnachrichten","Sprachauswahl","Übersetzergruppen"],
    "ar": ["الترحيب","مكافحة الإغراق","التصويت","التحقق","القيادة","الإشراف","المترجم","الأتمتة","قائمة الأدوار","الإشراف الذكي","مدير الفعاليات","مخطط الحرب","النشاط والترتيب","التدقيق والأمان","النسخ والاستعادة","شبكة الخوادم","التذاكر","السجلات","رسائل الأعضاء","اختيار اللغة","مجموعات الترجمة"],
    "fr": ["Bienvenue","AntiFlood","Votes","Vérification","Direction","Modération","Traducteur","Automatisations","Menu des rôles","AutoMod IA","Gestionnaire d’événements","Planificateur de guerre","Activité et classement","Audit et sécurité","Sauvegarde et restauration","Réseau interserveurs","Tickets","Journalisation","Messages privés","Sélection de langue","Groupes de traduction"],
    "it": ["Benvenuto","AntiFlood","Votazioni","Verifica","Leadership","Moderazione","Traduttore","Automazioni","Menu ruoli","AutoMod IA","Gestore eventi","Pianificatore di guerra","Attività e classifica","Audit e sicurezza","Backup e ripristino","Rete tra server","Ticket","Registrazione","Messaggi diretti","Selezione lingua","Gruppi di traduzione"],
    "pl": ["Powitanie","AntiFlood","Głosowania","Weryfikacja","Kierownictwo","Moderacja","Tłumacz","Automatyzacje","Menu ról","AI AutoMod","Menedżer wydarzeń","Planer wojny","Aktywność i ranking","Audyt i bezpieczeństwo","Kopia i przywracanie","Sieć międzyserwerowa","Zgłoszenia","Rejestrowanie","Wiadomości prywatne","Wybór języka","Grupy tłumaczeń"],
}

PLUGIN_KEYS = ["welcome","antiflood","voting","verification","leadership","moderation","translator","automations","role_menu","ai_automod","event_manager","war_planner","activity_ranking","audit_security","backup_restore","cross_guild_network","tickets","logging","guild_dm_broadcast","language_selection","translator_groups"]

PHRASES = {
    "en": ["Install plugin","Plugin settings","Protected channels","Add rule","Remove","Blocked message text","Leave empty to delete without a warning","Required exceptions","Search role","Search member","Runtime","Detection","Actions","Save settings","Role panels","Add role","Delete panel","Save all settings","Translation setup","Groups","Add group","Delete group","Add channel","Basic Discord commands","New poll","Create poll","Edit poll","Add language","Copy source","Answer text","Add option","Preview","Cancel","Polls","Edit","Publish","Close","Delete","Voting preview","War plans","Waves","Delete wave","Delete plan","Save all","Welcome flow","Discord message","Recent members","Refresh","Enabled","Disabled","Channel","Language","Group name","Default language","Loading…","No data","Active","Draft","Closed"],
    "uk": ["Установити плагін","Налаштування плагіна","Захищені канали","Додати правило","Видалити","Текст заблокованого повідомлення","Залиште порожнім, щоб видаляти без попередження","Обов’язкові винятки","Пошук ролі","Пошук учасника","Виконання","Виявлення","Дії","Зберегти налаштування","Панелі ролей","Додати роль","Видалити панель","Зберегти всі налаштування","Налаштування перекладу","Групи","Додати групу","Видалити групу","Додати канал","Основні команди Discord","Нове голосування","Створити голосування","Редагувати голосування","Додати мову","Копіювати джерело","Текст відповіді","Додати варіант","Попередній перегляд","Скасувати","Голосування","Редагувати","Опублікувати","Закрити","Видалити","Попередній перегляд голосування","Плани війни","Хвилі","Видалити хвилю","Видалити план","Зберегти все","Сценарій привітання","Повідомлення Discord","Останні учасники","Оновити","Увімкнено","Вимкнено","Канал","Мова","Назва групи","Мова за замовчуванням","Завантаження…","Немає даних","Активне","Чернетка","Закрите"],
    "ru": ["Установить плагин","Настройки плагина","Защищённые каналы","Добавить правило","Удалить","Текст заблокированного сообщения","Оставьте пустым для удаления без предупреждения","Обязательные исключения","Поиск роли","Поиск участника","Выполнение","Обнаружение","Действия","Сохранить настройки","Панели ролей","Добавить роль","Удалить панель","Сохранить все настройки","Настройка перевода","Группы","Добавить группу","Удалить группу","Добавить канал","Основные команды Discord","Новое голосование","Создать голосование","Редактировать голосование","Добавить язык","Копировать источник","Текст ответа","Добавить вариант","Предпросмотр","Отмена","Голосования","Редактировать","Опубликовать","Закрыть","Удалить","Предпросмотр голосования","Планы войны","Волны","Удалить волну","Удалить план","Сохранить всё","Сценарий приветствия","Сообщение Discord","Последние участники","Обновить","Включено","Отключено","Канал","Язык","Название группы","Язык по умолчанию","Загрузка…","Нет данных","Активно","Черновик","Закрыто"],
    "de": ["Plugin installieren","Plugin-Einstellungen","Geschützte Kanäle","Regel hinzufügen","Entfernen","Text der blockierten Nachricht","Leer lassen, um ohne Warnung zu löschen","Erforderliche Ausnahmen","Rolle suchen","Mitglied suchen","Laufzeit","Erkennung","Aktionen","Einstellungen speichern","Rollenbereiche","Rolle hinzufügen","Bereich löschen","Alle Einstellungen speichern","Übersetzung einrichten","Gruppen","Gruppe hinzufügen","Gruppe löschen","Kanal hinzufügen","Grundlegende Discord-Befehle","Neue Abstimmung","Abstimmung erstellen","Abstimmung bearbeiten","Sprache hinzufügen","Quelle kopieren","Antworttext","Option hinzufügen","Vorschau","Abbrechen","Abstimmungen","Bearbeiten","Veröffentlichen","Schließen","Löschen","Abstimmungsvorschau","Kriegspläne","Wellen","Welle löschen","Plan löschen","Alles speichern","Willkommensablauf","Discord-Nachricht","Neue Mitglieder","Aktualisieren","Aktiviert","Deaktiviert","Kanal","Sprache","Gruppenname","Standardsprache","Wird geladen…","Keine Daten","Aktiv","Entwurf","Geschlossen"],
    "ar": ["تثبيت الإضافة","إعدادات الإضافة","القنوات المحمية","إضافة قاعدة","إزالة","نص الرسالة المحظورة","اتركه فارغًا للحذف دون تحذير","الاستثناءات المطلوبة","البحث عن دور","البحث عن عضو","التشغيل","الاكتشاف","الإجراءات","حفظ الإعدادات","لوحات الأدوار","إضافة دور","حذف اللوحة","حفظ جميع الإعدادات","إعداد الترجمة","المجموعات","إضافة مجموعة","حذف المجموعة","إضافة قناة","أوامر Discord الأساسية","تصويت جديد","إنشاء تصويت","تعديل التصويت","إضافة لغة","نسخ المصدر","نص الإجابة","إضافة خيار","معاينة","إلغاء","التصويتات","تعديل","نشر","إغلاق","حذف","معاينة التصويت","خطط الحرب","الموجات","حذف الموجة","حذف الخطة","حفظ الكل","تدفق الترحيب","رسالة Discord","الأعضاء الجدد","تحديث","مُمكّن","معطّل","القناة","اللغة","اسم المجموعة","اللغة الافتراضية","جارٍ التحميل…","لا توجد بيانات","نشط","مسودة","مغلق"],
    "fr": ["Installer le plugin","Paramètres du plugin","Canaux protégés","Ajouter une règle","Retirer","Texte du message bloqué","Laisser vide pour supprimer sans avertissement","Exceptions requises","Rechercher un rôle","Rechercher un membre","Exécution","Détection","Actions","Enregistrer les paramètres","Panneaux de rôles","Ajouter un rôle","Supprimer le panneau","Tout enregistrer","Configuration de la traduction","Groupes","Ajouter un groupe","Supprimer le groupe","Ajouter un canal","Commandes Discord de base","Nouveau vote","Créer le vote","Modifier le vote","Ajouter une langue","Copier la source","Texte de réponse","Ajouter une option","Aperçu","Annuler","Votes","Modifier","Publier","Fermer","Supprimer","Aperçu du vote","Plans de guerre","Vagues","Supprimer la vague","Supprimer le plan","Tout enregistrer","Parcours de bienvenue","Message Discord","Membres récents","Actualiser","Activé","Désactivé","Canal","Langue","Nom du groupe","Langue par défaut","Chargement…","Aucune donnée","Actif","Brouillon","Fermé"],
    "it": ["Installa plugin","Impostazioni plugin","Canali protetti","Aggiungi regola","Rimuovi","Testo del messaggio bloccato","Lascia vuoto per eliminare senza avviso","Eccezioni richieste","Cerca ruolo","Cerca membro","Esecuzione","Rilevamento","Azioni","Salva impostazioni","Pannelli dei ruoli","Aggiungi ruolo","Elimina pannello","Salva tutte le impostazioni","Configurazione traduzione","Gruppi","Aggiungi gruppo","Elimina gruppo","Aggiungi canale","Comandi Discord di base","Nuova votazione","Crea votazione","Modifica votazione","Aggiungi lingua","Copia origine","Testo risposta","Aggiungi opzione","Anteprima","Annulla","Votazioni","Modifica","Pubblica","Chiudi","Elimina","Anteprima votazione","Piani di guerra","Ondate","Elimina ondata","Elimina piano","Salva tutto","Flusso di benvenuto","Messaggio Discord","Membri recenti","Aggiorna","Abilitato","Disabilitato","Canale","Lingua","Nome gruppo","Lingua predefinita","Caricamento…","Nessun dato","Attivo","Bozza","Chiuso"],
    "pl": ["Zainstaluj wtyczkę","Ustawienia wtyczki","Chronione kanały","Dodaj regułę","Usuń","Tekst zablokowanej wiadomości","Pozostaw puste, aby usuwać bez ostrzeżenia","Wymagane wyjątki","Szukaj roli","Szukaj członka","Środowisko","Wykrywanie","Działania","Zapisz ustawienia","Panele ról","Dodaj rolę","Usuń panel","Zapisz wszystkie ustawienia","Konfiguracja tłumaczenia","Grupy","Dodaj grupę","Usuń grupę","Dodaj kanał","Podstawowe polecenia Discord","Nowe głosowanie","Utwórz głosowanie","Edytuj głosowanie","Dodaj język","Kopiuj źródło","Tekst odpowiedzi","Dodaj opcję","Podgląd","Anuluj","Głosowania","Edytuj","Opublikuj","Zamknij","Usuń","Podgląd głosowania","Plany wojny","Fale","Usuń falę","Usuń plan","Zapisz wszystko","Proces powitalny","Wiadomość Discord","Ostatni członkowie","Odśwież","Włączono","Wyłączono","Kanał","Język","Nazwa grupy","Język domyślny","Ładowanie…","Brak danych","Aktywne","Szkic","Zamknięte"],
}

UKRAINIAN_ALIASES = {
    "Установити плагін": 0, "Групи мов": 19,
    "Публікувати пост у вибраній темі": 35, "Видалити групу": 21,
    "Додати групу": 20, "Зберегти налаштування": 13,
    "Предпросмотр": 31, "Предпросмотр голосования": 38,
}

def phrase_catalog(code):
    result = dict(zip(PHRASES["en"], PHRASES[code]))
    for source, index in UKRAINIAN_ALIASES.items():
        result[source] = PHRASES[code][index]
    return result

def replace_values(value, translations):
    if isinstance(value, dict):
        return {key: replace_values(item, translations) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_values(item, translations) for item in value]
    if isinstance(value, str):
        return translations.get(value, value)
    return value

def main():
    english = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    english["plugin_names"] = dict(zip(PLUGIN_KEYS, ["Welcome","AntiFlood","Voting","Verification","Leadership","Moderation","Translator","Automations","Role Menu","AI AutoMod","Event Manager","War Planner","Activity & Ranking","Audit & Security","Backup & Restore","Cross-Guild Network","Tickets","Logging","Guild DM Broadcast","Language Selection","Translator Groups"]))
    english["_phrases"] = dict(zip(PHRASES["en"], PHRASES["en"]))
    (LOCALES / "en.json").write_text(json.dumps(english, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for code in ("uk", "ru"):
        path = LOCALES / f"{code}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["plugin_names"] = dict(zip(PLUGIN_KEYS, PLUGIN_NAMES[code]))
        document["_phrases"] = phrase_catalog(code)
        document["_language"]["version"] = 3
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for code, (icon, name, english_name, discord, rtl) in LANGUAGES.items():
        document = replace_values(copy.deepcopy(english), TRANSLATIONS[code])
        document["_language"] = {"code":code,"icon":icon,"name":name,"english_name":english_name,"discord_locale":discord,"rtl":rtl,"version":3}
        document["plugin_names"] = dict(zip(PLUGIN_KEYS, PLUGIN_NAMES[code]))
        document["_phrases"] = phrase_catalog(code)
        (LOCALES / f"{code}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
