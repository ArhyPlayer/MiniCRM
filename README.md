# Mini CRM

Десктопная CRM-система с FastAPI-бэкендом, Tkinter-интерфейсом и интеграцией Google Drive / Google Sheets для экспорта отчётов.

---

## Возможности

- Управление **клиентами**, **сделками** и **задачами** (создание, редактирование, архивация, удаление)
- **Поиск** по всем сущностям
- **Чекбоксы** для выборочных и пакетных операций (архивация/удаление/экспорт нескольких записей сразу)
- **Экспорт в Google Sheets** прямо из интерфейса: создаётся оформленная таблица с заголовком, блоком аналитики и данными
- Бэкенд в **Docker** с горячей перезагрузкой при изменении кода
- Скрипт заполнения тестовыми данными

---

## Структура проекта

```
GooAutoSheets/
├── backend/
│   ├── api.py            # FastAPI — 20 REST-эндпоинтов (клиенты, сделки, задачи)
│   ├── database.py       # CRMDatabase — все CRUD-операции через SQLite 3
│   ├── models.py         # DDL-схемы таблиц + Pydantic-модели
│   └── Dockerfile        # Образ для бэкенда
├── integrations/
│   ├── google_sheets_client.py   # Google Sheets API v4 (сервисный аккаунт)
│   ├── google_drive_client.py    # Google Drive API v3 (сервисный аккаунт + OAuth2)
│   └── report_app.py             # Прототип генератора отчётов
├── data/
│   ├── crm.db            # SQLite-база (создаётся автоматически, не в git)
│   └── google_settings.json  # Пути к ключам Google (сохраняются через GUI)
├── credentials/          # JSON-ключи Google (не в git)
├── start_gui.py          # Tkinter-приложение (главный файл запуска GUI)
├── seed_data.py          # Скрипт генерации тестовых данных
├── docker-compose.yml    # Оркестрация бэкенда
├── requirements.txt      # Зависимости Python
└── env-example           # Шаблон переменных окружения
```

---

## Быстрый старт

### 1. Виртуальное окружение

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Запустить бэкенд (Docker)

```bash
docker compose up -d
```

Бэкенд поднимается на `http://localhost:8000`. При изменении файлов в `backend/` сервер перезапускается автоматически.

Проверить работу: `http://localhost:8000/docs` — Swagger UI со всеми эндпоинтами.

### 3. Запустить GUI

```bash
python start_gui.py
```

---

## Заполнить базу тестовыми данными

```bash
# Стандартно — ~1000 записей в каждую таблицу
python seed_data.py

# Задать количество вручную
python seed_data.py --count 500

# Другой адрес бэкенда
python seed_data.py --url http://localhost:8000
```

---

## Интерфейс

### Вкладки

| Вкладка | Описание |
|---|---|
| Дашборд | Общая статистика: клиенты, сделки, задачи |
| Клиенты | Список клиентов с фильтром по статусу |
| Сделки | Список сделок с фильтром по статусу |
| Задачи | Список задач с фильтром по статусу |

### Тулбар каждой вкладки

**Строка 1 — поиск и выбор:**
```
[Поиск: ___] | [☑ Все] [☐ Снять] [Выбрано: N / M] | [Фильтр статуса ▾]
```

**Строка 2 — действия:**
```
[＋ Добавить] [✎ Редактировать] [✕ Удалить] [📦 Архив] | [📊 Выгрузить в Google]   ⟳
```

### Чекбоксы и пакетные операции

- **Кликнуть ☐ в строке** — отметить/снять одну запись
- **☑ Все** — отметить все строки на вкладке
- **☐ Снять** — снять все отметки
- **Удалить / Архивировать / Выполнить** — при наличии отметок применяется ко **всем отмеченным**; если ничего не отмечено — к выбранной строке
- **📊 Выгрузить в Google** — экспортирует отмеченные строки (или все, если ничего не выбрано)

---

## Экспорт в Google Sheets

### Структура создаваемой таблицы

```
Строка 1  │ ОТЧЁТ: Клиенты              (слитые ячейки, синий фон, белый жирный 14pt)
Строка 2  │ Дата формирования: …        (серый курсив)
Строка 3  │ (пусто)
Строка 4  │ АНАЛИЗ ДАННЫХ               (слитые, голубовато-серый фон, жирный)
Строка 5  │ (пусто)
Строки 6… │ Метрика  │  Значение        (аналитика по статусам и суммам)
…         │ (2 пустых строки)
Строка N  │ ID │ Имя │ … │ Статус       (синий заголовок, закреплён при скролле)
Строки …  │ данные                      (чередующиеся полосы)
```

### Настройка Google (кнопка ⚙ Google в шапке)

| Поле | Описание |
|---|---|
| OAuth Client Secret JSON | Файл `client_secret_*.json` — для создания таблицы от имени пользователя |
| Service Account JSON | Файл ключа сервисного аккаунта — для записи данных |
| ID папки Drive | *(Опционально)* ID папки, куда сохранять таблицы |

Настройки сохраняются в `data/google_settings.json` и загружаются автоматически при следующем запуске.

### Подготовка ключей Google

**OAuth 2.0 (для создания файлов от имени пользователя):**
1. [Google Cloud Console](https://console.cloud.google.com/) → API и сервисы → Учётные данные
2. Создать **OAuth 2.0 Client ID** → тип «Desktop app»
3. Скачать JSON, указать путь в настройках GUI
4. При первом экспорте откроется браузер — авторизуйтесь; токен сохранится в `credentials/token_drive.json`

**Сервисный аккаунт (для записи данных):**
1. Google Cloud Console → IAM → Сервисные аккаунты → Создать → скачать JSON-ключ
2. Включить **Google Sheets API** и **Google Drive API**
3. Расшарить целевую папку Drive на email сервисного аккаунта (роль «Редактор»)
4. Указать путь к ключу в настройках GUI

---

## API бэкенда

Бэкенд доступен по адресу `http://localhost:8000`. Полная документация: `http://localhost:8000/docs`.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/dashboard` | Общая статистика |
| GET / POST | `/clients` | Список / создание клиентов |
| GET / PUT / DELETE | `/clients/{id}` | Получить / обновить / удалить клиента |
| POST | `/clients/{id}/archive` | Архивировать клиента |
| GET | `/clients/search` | Поиск клиентов (iLike) |
| GET / POST | `/deals` | Список / создание сделок |
| GET / PUT / DELETE | `/deals/{id}` | Получить / обновить / удалить сделку |
| GET | `/deals/search` | Поиск сделок |
| GET / POST | `/tasks` | Список / создание задач |
| GET / PUT / DELETE | `/tasks/{id}` | Получить / обновить / удалить задачу |
| POST | `/tasks/{id}/complete` | Отметить задачу выполненной |
| POST | `/tasks/{id}/reopen` | Переоткрыть задачу |

---

## Модули Google-интеграции

Находятся в `integrations/` и используются напрямую из GUI.

### `google_sheets_client.py`

```python
from google_sheets_client import GoogleSheetsClient

client = GoogleSheetsClient(
    spreadsheet_id="<ID таблицы>",
    credentials_path="excel-factory-key.json",
)
client.default_sheet = client.get_sheet_names()[0]  # автоопределение имени листа

client.write_range("A1", [["Имя", "Сумма"], ["Иванов", 50000]])
client.read_all()
client.get_sheet_names()
client.get_sheet_id()
client.batch_update([...])
```

### `google_drive_client.py`

```python
from google_drive_client import GoogleDriveOAuthClient

oauth = GoogleDriveOAuthClient(
    client_secret_path="client_secret_*.json",
    token_path="credentials/token_drive.json",
)
meta = oauth.create_spreadsheet("Отчёт за март 2026", folder_id="<FOLDER_ID>")
print(meta["id"])           # передаётся в GoogleSheetsClient
print(meta["webViewLink"])  # ссылка для открытия
```

---

## Требования

- Python 3.10+
- Docker Engine (для бэкенда)
- Зависимости: `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `requests`, `watchfiles`, `google-api-python-client`, `google-auth`, `google-auth-oauthlib`, `python-dotenv`
