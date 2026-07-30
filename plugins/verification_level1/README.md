# ShieldNet — Verification Level 1 v1.0.1

Плагін реалізує:

- самоверифікацію через кнопку, slash-команду або текстову команду;
- введення альянсу та імені;
- повністю редаговану маску `{ALLIANCE}` / `{NICKNAME}`;
- зміну альянсу й імені командою `rename`;
- призначення вибраної ролі під час verify та rename;
- привітальне повідомлення у каналі верифікації;
- автоматичне видалення привітання, стандартно через 300 секунд;
- видалення текстової команди користувача;
- журнал і PostgreSQL-історію;
- API налаштувань та Angular-компонент.

## Приклади

```text
!verify EVEX Roman
!rename PACY Alex
```

Маска:

```text
[{ALLIANCE}] {NICKNAME}
```

Результат:

```text
[EVEX] Roman
```

## Встановлення

```bash
tar -xzf shieldnet-verification-level1-v1.0.0.tar.gz
cd shieldnet-verification-level1
chmod +x install.sh
./install.sh
```

## Підключення backend router

Якщо ShieldNet не підключає router із `manifest.json` автоматично:

```python
from plugins.verification_level1.backend.router import router as verification_level1_router
app.include_router(verification_level1_router, prefix="/api")
```

## Підключення runtime

Loader повинен завантажити `runtime.py` та виконати:

```python
await module.setup(bot, services)
```

При вимкненні:

```python
await module.teardown(bot)
```

## Публікація кнопки

Після завантаження runtime:

```python
runtime = module.get_runtime()
await runtime.publish_verification_message(guild)
```

Цю дію варто прив'язати до кнопки «Опублікувати повідомлення» у вебпанелі.

## Важливо для Discord

Роль бота повинна бути вище ролі, яку він призначає, і вище користувачів,
яким він змінює nickname. Боту потрібні `Manage Nicknames`, `Manage Roles`,
`Send Messages` і, для видалення команд, `Manage Messages`.


## Автоматичне визначення PostgreSQL

`install.sh` автоматично читає налаштування з `/etc/shieldnet`.

Підтримуються готові DSN:

```text
DATABASE_URL
POSTGRES_DSN
DB_DSN
SQLALCHEMY_DATABASE_URI
```

Або окремі параметри:

```text
POSTGRES_USER / DB_USER
POSTGRES_PASSWORD / DB_PASSWORD
POSTGRES_HOST / DB_HOST
POSTGRES_PORT / DB_PORT
POSTGRES_DB / DB_NAME
```

Пошук виконується рекурсивно у файлах `.env`, `*.env`, `*.conf`, `*.ini`,
`*.cfg`, `config`, `settings` всередині `/etc/shieldnet`.
