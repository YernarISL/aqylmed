# AQYLMED — бэкенд (MVP, Release 1)

Бэкенд для симулятора клинических кейсов и RAG-чатбота по учебникам.
Стек: FastAPI + SQLAlchemy (SQLite/Postgres) + Gemini (`google-genai`) + numpy для векторного поиска.
За основу взят прототип `clinical_sim`, доработанный под user stories из TSIS 6-7.

## Запуск

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                 # вписать GEMINI_API_KEY и JWT_SECRET
python -m scripts.load_cases           # 6 шаблонов из data/cases (5 published + 1 draft)
python -m scripts.create_user --email admin@aqylmed.kz --password admin12345 --role admin
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs → кнопка **Authorize** (username = email).

Без ключа и интернета: `LLM_PROVIDER=mock` — офлайн-пациент, экстрактивные ответы бота, эмбеддинги «мешок слов».
По разделу 9 TSIS 6-7 (бюджет $0) этот режим используется для тестов и демо, когда закончилась квота.

Тесты (39 шт., покрывают GWT-сценарии из TSIS 6-7): `pytest -q`

## API ↔ user stories

| Story | Эндпоинт | Что проверяется |
|---|---|---|
| Sign-in (энейблер) | `POST /api/v1/auth/register`, `/login`, `GET /auth/me` | JWT, роли student / teacher / admin |
| US-01 Каталог | `GET /api/v1/cases` | только `published`, карточка: специальность, сложность, жалоба |
| US-11 Фильтр | `GET /api/v1/cases?specialty=…`, `GET /cases/specialties` | `count` совпадает с числом карточек |
| US-02 Старт кейса | `POST /api/v1/attempts` `{case_id, force}` | возраст и витальные показатели — случайно в диапазонах шаблона; одна активная попытка (409 → диалог → `force=true`); draft → 404 «Case not available» |
| US-03 Опрос пациента | `POST /api/v1/attempts/{id}/questions` | LLM видит только лист фактов; вопрос сопоставляется с 8 категориями ключевых вопросов и пишется в лог; пустой ввод → 422 |
| US-13 Обследования | `GET /api/v1/tests`, `POST /attempts/{id}/tests` | результат только из шаблона (без LLM), остальное — «норма» |
| US-04 Диагноз | `GET /api/v1/icd10?q=…`, `POST /attempts/{id}/submit` | код из МКБ-10, после отправки попытка read-only (409) |
| US-07 Оценка | ответ `submit` | 40 анамнез + 20 обследования + 40 диагноз; смежный диагноз = 20; детерминировано |
| US-08 Обратная связь | ответ `submit`, `GET /attempts/{id}` | каждый упущенный вопрос/обследование со ссылкой на фрагмент учебника |
| US-09 История | `GET /api/v1/attempts` | только свои завершённые, новые сверху |
| US-10 Учебники | `POST /api/v1/textbooks` (admin, PDF) | фон: текст → куски по страницам → эмбеддинги; статус `processing → ready/failed` |
| US-05 Чатбот | `POST /api/v1/chat/ask` | top-5 фрагментов; ниже порога 0.75 → fallback **без вызова LLM**; ≤ 150 слов |
| US-06 Цитаты | `citations[]`, `GET /textbooks/{id}/chunks/{chunk_id}` | книга, глава, страница, дословный фрагмент |
| Преподаватель/SME | `/api/v1/admin/cases…` (`generate`, `PUT`, `publish`) | ИИ пишет только черновик; студенты видят кейс после публикации |
| QA (NFR-02) | `GET /api/v1/chat/logs` | медиана/максимум времени ответа, доля fallback |

## Как устроено

```
app/
  main.py            — сборка приложения
  config.py          — настройки, каталог обследований, веса оценки
  models.py          — таблицы: users, clinic_cases, attempts, attempt_events, textbooks, text_chunks, chat_logs
  schemas.py         — CaseTemplate (формат шаблона кейса) и тела запросов
  security.py        — PBKDF2-пароли, JWT, проверка ролей
  prompts.py         — промпты пациента, классификатора, RAG, генерации кейсов
  routers/           — auth, cases, attempts, textbooks, chat
  services/
    llm.py           — Gemini / mock: generate(), embed()
    patient.py       — генерация пациента, ответы, сопоставление с ключевыми вопросами
    scoring.py       — формула оценки + обратная связь
    rag.py           — индексация PDF, векторный поиск, ответы с цитатами
    icd10.py         — справочник МКБ-10 (app/data/icd10.json)
data/cases/*.json    — шаблоны кейсов
scripts/             — load_cases, create_user
tests/               — pytest, офлайн (mock)
```

Ключевые решения:

* **Пациент не может «проболтаться»**: в промпт идёт только лист фактов: без диагноза, результатов анализов и ключевых вопросов. Результаты обследований выдаются из БД, LLM в этом не участвует.
* **Оценка детерминирована**: категория ключевого вопроса вычисляется один раз, когда студент задаёт вопрос, и сохраняется в лог. `scoring.score()` — чистая функция от лога и шаблона, без LLM. Сопоставление: сначала ключевые слова из шаблона, при отсутствии совпадений — LLM-классификатор. Он работает параллельно с ответом пациента, поэтому задержка не суммируется.
* **RAG без отдельной векторной БД**: для двух учебников (решение 2 на груминге) эмбеддинги хранятся в таблице, поиск идёт по матрице numpy в памяти. При росте корпуса можно перейти на pgvector, API от этого не изменится. Куски не пересекают границу страницы, поэтому у каждой цитаты точный номер страницы. Главы берутся из оглавления PDF, а если его нет — из строк вида «Chapter N»/«Глава N».
* **Порог 0.75** — стартовое значение для `gemini-embedding-001`. Его нужно подстроить через `RAG_MIN_SIMILARITY` на 20 тестовых вопросах QA (см. `/chat/logs` → `best_similarity`).

## Что осталось за другими ролями / открытые вопросы

* **SME**: проверить 6 шаблонов в `data/cases` (клиническое содержание, диапазоны витальных показателей, связанные коды МКБ-10, веса оценки D-5). Кейсы помечены `published`, только чтобы закрыть US-01 в демо. По правилам TSIS 6-7 до проверки их нужно перевести в `draft`.
* **PM**: одобренные PDF учебников (Internal Medicine, Anatomy) с подтверждёнными правами.
* **QA**: 20 вопросов для настройки порога и замера NFR-02 (≤ 5 с, медиана ≤ 3 с) на реальном Gemini.
* **EN-02 (spike)**: проверить на 30 вопросах, что Gemini-пациент не выходит за лист фактов.
* Справочник МКБ-10 — подборка из ~90 кодов по темам курса. Полный справочник кладётся в `app/data/icd10.json` в том же формате.
* Миграции: пока `create_all`. Перед продом с Postgres стоит добавить Alembic.
