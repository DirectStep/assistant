# Personal Assistant

Однопользовательский Telegram-бот и Telegram Mini App для задач и ежедневных новостных PDF-сводок.

Реализованы Phase 1–9: backend, Telegram-бот, извлечение явно указанных метаданных задачи, Telegram Mini App с Kanban/CRUD/настройками, новостной RSS/Atom pipeline, ежедневная PDF-сводка, автоматическая доставка, архив и production webhook/deployment-конфигурация.

## Требования

- Docker Desktop с Docker Compose
- либо Python 3.12+ и Node.js 24+ для запуска без контейнеров

## Быстрый запуск Phase 1–8

1. Скопируйте `.env.example` в `.env`.
2. Не вставляйте в `.env` токен, опубликованный в сообщениях или логах. Сначала перевыпустите его через BotFather.
3. Запустите окружение:

   ```bash
   docker compose up --build
   ```

4. Проверьте backend:

   ```text
   http://localhost:8000/api/health
   ```

5. Откройте frontend-заглушку:

   ```text
   http://localhost:5173
   ```

Backend-контейнер автоматически выполняет `alembic upgrade head` перед запуском FastAPI.

Если заданы `TELEGRAM_BOT_TOKEN` и `OWNER_TELEGRAM_ID`, backend одновременно запускает бота через polling. Доступны команды `/start`, `/tasks`, `/today`, `/news`, `/app`, `/help`; текст, forwarded message и voice создают задачи. После создания задачу можно завершить или удалить inline-кнопкой.

AI-провайдер выбирается через `LLM_PROVIDER=openai|gigachat`. Оба варианта включают
извлечение дедлайна/важности, обработку новостей и voice transcription. Без ключа выбранного
провайдера текст и forwarded message всё равно сохраняются как есть.

`POST /api/digests/generate` собирает реальные статьи за последние 24 часа, удаляет дубли,
ранжирует их и сохраняет одну сводку на текущую дату. Без настроенного AI-провайдера
используются заголовки/описания источников и локальный ranking.

После успешной генерации PDF сохраняется в `DIGEST_OUTPUT_DIR` под именем `daily_digest_YYYY-MM-DD.pdf`. Скачать существующий файл можно через защищённый `GET /api/digests/{date}/pdf`. В production-контейнере PDF собирает Jinja2 + WeasyPrint; при нативном запуске на Windows без GTK автоматически используется локальный ReportLab fallback.

Архив доступен через `GET /api/digests`, отдельная сводка — через `GET /api/digests/{date}`. Вкладка «Сводки» показывает даты, короткий HTML-view по разделам и кнопку загрузки PDF.

APScheduler каждую минуту сверяет локальное время с настройками пользователя. В нужную минуту бот один раз за календарную дату отправляет список задач и PDF. Повторный запуск не создаёт вторую сводку и не дублирует доставку. `/news` возвращает сегодняшний готовый PDF, а при его отсутствии запускает генерацию.

Mini App отправляет backend заголовок `Authorization: tma <Telegram initData>`. Backend проверяет HMAC-подпись, свежесть данных и owner ID. Для браузерной локальной разработки используется только `DEV_AUTH=true` + `DEV_TELEGRAM_USER_ID`; production-конфигурация такой bypass запрещает.

 Telegram открывает Mini App только по публичному HTTPS URL. После публикации frontend укажите адрес в `WEBAPP_URL`: при старте backend сам выставит в Telegram кнопку меню `Задачи` и добавит такую же inline-кнопку в `/start` и `/app`. Если URL локальный или не-HTTPS, бот оставляет стандартное меню команд — `http://localhost:5173` предназначен только для браузерной разработки.

Для временного локального теста несколькими пользователями можно явно установить `BOT_ALLOW_ALL_USERS=true`. В production оставляйте `false` и обязательно указывайте `OWNER_TELEGRAM_ID`.

## Локальный backend без Docker

Обычно PostgreSQL должен быть запущен и доступен по `DATABASE_URL`. Для временного локального smoke test допустим `DATABASE_URL=sqlite+aiosqlite:///./personal_assistant_dev.db`; production остаётся на PostgreSQL.

```bash
cd backend
python3 -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Проверки

```bash
cd backend
python3 -m compileall app alembic tests
ruff check .
pytest
```

```bash
cd frontend
npm install
npm run lint
npm run build
```

## Создание Telegram-бота

1. Откройте `@BotFather`, выполните `/newbot` и задайте имя/username.
2. Сохраните выданный токен только в `.env` как `TELEGRAM_BOT_TOKEN`.
3. Если токен попал в чат, скриншот, commit или лог, выполните в BotFather `/revoke` и используйте новый. Старый токен больше не считается секретным.
4. Узнайте числовой Telegram ID через `@userinfobot` и запишите его в `OWNER_TELEGRAM_ID`.
5. После первого запуска отправьте своему боту `/start`. Backend сам установит команды и кнопку Mini App.

Локально можно временно разрешить сообщения от всех через `BOT_ALLOW_ALL_USERS=true`. В production этот режим намеренно запрещён: верните `false`.

## Настройка Mini App

Telegram принимает только публичный HTTPS URL. Для постоянной работы нужен домен с TLS, например `https://assistant.example.com`.

1. Запишите один HTTPS-адрес в `APP_BASE_URL` и `WEBAPP_URL`.
2. В BotFather откройте `/mybots` → бот → **Bot Settings** → **Menu Button** → **Configure menu button** и укажите этот URL.
3. Перезапустите backend. Он дополнительно установит кнопку через Bot API.
4. Временный tunnel годится только для проверки: его адрес может исчезнуть после остановки процесса.

Mini App отправляет `Telegram.WebApp.initData` в заголовке `Authorization: tma ...`. Backend проверяет подпись и не доверяет ID из браузера.

## Полная настройка `.env`

```bash
cp .env.example .env
```

Обязательные production-значения:

```env
TELEGRAM_BOT_TOKEN=новый_токен_BotFather
OWNER_TELEGRAM_ID=ваш_числовой_id
POSTGRES_PASSWORD=длинный_случайный_пароль
LLM_PROVIDER=gigachat
GIGACHAT_AUTH_KEY=authorization_key_из_кабинета_GigaChat_API
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_TASK_MODEL=GigaChat-2
GIGACHAT_NEWS_MODEL=GigaChat-2-Pro
APP_BASE_URL=https://assistant.example.com
WEBAPP_URL=https://assistant.example.com
BOT_MODE=webhook
TELEGRAM_WEBHOOK_SECRET=случайная_строка_из_букв_цифр_дефисов_и_подчеркиваний
APP_ENV=production
CORS_ORIGINS=https://assistant.example.com
DEV_AUTH=false
BOT_ALLOW_ALL_USERS=false
TIMEZONE=Europe/Moscow
DAILY_DIGEST_TIME=08:30
NEWS_MAX_ARTICLES=10
```

Без ключа выбранного AI-провайдера текстовые задачи, RSS, локальное ранжирование, PDF и
Mini App работают. Voice transcription и качественные structured summaries требуют ключ.

## PostgreSQL и миграции

В Docker PostgreSQL поднимается автоматически. Отдельный запуск только базы:

```bash
docker compose up -d postgres
```

Применить миграции вручную:

```bash
cd backend
python3 -m alembic upgrade head
python3 -m alembic current
```

Backend-контейнер выполняет `alembic upgrade head` при каждом старте. PDF и данные PostgreSQL лежат в именованных Docker volumes и не исчезают при пересборке контейнера.

## Polling и webhook

- `BOT_MODE=polling` — локальная разработка. Публичный callback не нужен.
- `BOT_MODE=webhook` — production. Telegram отправляет update на `APP_BASE_URL/api/telegram/webhook`, запрос защищён `TELEGRAM_WEBHOOK_SECRET`.
- При временной недоступности Telegram API FastAPI продолжает работать, а настройка polling/webhook повторяется в фоне.
- Запускайте только один backend-контейнер: в MVP scheduler встроен в процесс.

## Production-контейнеры

Production-конфигурация собирает React в статические файлы, раздаёт их через nginx и проксирует `/api` к backend:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### Деплой на VPS

1. Направьте DNS A-запись домена на IP VPS.
2. Установите Docker Engine, Compose plugin, nginx и certbot.
3. Склонируйте репозиторий, создайте `.env` и заполните production-значения выше.
4. Поднимите приложение, доступное только локальному nginx:

   ```bash
   docker compose -f docker-compose.prod.yml up --build -d
   docker compose -f docker-compose.prod.yml ps
   ```

5. Создайте `/etc/nginx/sites-available/personal-assistant`:

   ```nginx
   server {
       listen 80;
       server_name assistant.example.com;
       client_max_body_size 8m;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

6. Включите конфигурацию, получите сертификат и перезапустите backend после окончательной смены URL:

   ```bash
   sudo ln -s /etc/nginx/sites-available/personal-assistant /etc/nginx/sites-enabled/personal-assistant
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d assistant.example.com
   docker compose -f docker-compose.prod.yml restart backend
   ```

7. Проверьте `https://assistant.example.com/api/health`, `/start`, `/app`, `/news` и кнопку меню.

Обновление:

```bash
git pull
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

## Утреннее расписание

`DAILY_DIGEST_TIME=08:30` трактуется в `TIMEZONE`. Экран «Настройки» сохраняет пользовательское время и часовой пояс в БД; scheduler читает их каждую минуту. Если Telegram или новости кратко недоступны, отправка повторяется в безопасном двухчасовом окне. После успешной доставки дата фиксируется, поэтому повторов в этот день нет.

## Ограничения MVP

- Один владелец и один встроенный scheduler.
- RSS/Atom зависят от доступности источников; сайты без нормального feed не скрапятся.
- Без настроенного AI-провайдера используются исходные описания и локальная оценка релевантности.
- Нет календаря, проектов, тегов, recurring tasks, командной работы и полноценного news reader.
- Временный HTTPS tunnel не заменяет VPS с постоянным доменом.

## Переменные окружения Phase 1–9

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — единый источник параметров БД для PostgreSQL и backend.
- `POSTGRES_HOST`, `POSTGRES_PORT` — адрес БД; в Docker используется `postgres:5432`, а при локальном backend обычно `localhost:5432`.
- `POSTGRES_HOST_PORT` — порт PostgreSQL, опубликованный на хосте в development.
- `HTTP_PORT` — локальный порт production nginx-контейнера; по умолчанию `8080`.
- `DATABASE_URL` — необязательный полный async SQLAlchemy URL; если задан, он имеет приоритет, а спецсимволы логина/пароля должны быть URL-encoded.
- `APP_BASE_URL`, `WEBAPP_URL` — внешние адреса backend/frontend.
- `TIMEZONE`, `DAILY_DIGEST_TIME` — часовой пояс и время автоматической утренней доставки.
- `OWNER_TELEGRAM_ID` — единственный разрешённый Telegram user ID.
- `BOT_ALLOW_ALL_USERS` — опасный тестовый режим без owner-фильтра; по умолчанию `false`.
- `TELEGRAM_BOT_TOKEN` — токен BotFather; хранится только в `.env`.
- `TELEGRAM_API_IP` — необязательный доступный IP Telegram Bot API для VPS, где
  стандартный DNS возвращает недоступный edge; имя `api.telegram.org` сохраняется для TLS.
- `BOT_MODE` — `polling` локально или `webhook` на VPS.
- `TELEGRAM_WEBHOOK_SECRET` — секрет проверки production webhook.
- `DEV_AUTH`, `DEV_TELEGRAM_USER_ID` — только локальный обход Telegram initData; в production запрещён.
- `LLM_PROVIDER` — активный провайдер: `openai` или `gigachat`.
- `GIGACHAT_AUTH_KEY` — Authorization Key проекта GigaChat API; access token обновляется автоматически.
- `GIGACHAT_SCOPE`, `GIGACHAT_TASK_MODEL`, `GIGACHAT_NEWS_MODEL` — тариф и модели GigaChat.
- Официальные сертификаты НУЦ Минцифры устанавливаются в backend-образ при сборке;
  TLS-проверка GigaChat в production не отключается.
- `OPENAI_API_KEY` — ключ запасного OpenAI-провайдера.
- `OPENAI_TASK_MODEL`, `OPENAI_TRANSCRIPTION_MODEL`, `OPENAI_NEWS_MODEL` — модели для извлечения задач, voice и обработки новостей.
- `NEWS_MAX_ARTICLES` — целевое количество материалов в ежедневной сводке.
- `DIGEST_OUTPUT_DIR` — каталог постоянного хранения PDF-файлов.

Подробная архитектура и критерии всех этапов находятся в [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
