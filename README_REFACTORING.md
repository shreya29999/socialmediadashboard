# Social Media Dashboard — Refactored Structure

This branch is a structural refactor of the existing working code.

## Goal

Keep the existing API behavior and frontend content while separating the monolithic `main.py`,
database layer, AI logic, email service, and Celery worker code into modules.

## New structure

```text
socialmediadashboard/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── social_accounts.py
│   │       ├── media.py
│   │       ├── users.py
│   │       ├── posts.py
│   │       ├── approvals.py
│   │       ├── analytics.py
│   │       ├── calendar.py
│   │       ├── ai.py
│   │       ├── admin.py
│   │       ├── superadmin.py
│   │       └── notifications.py
│   ├── core/
│   │   ├── config.py
│   │   ├── helpers.py
│   │   ├── logging.py
│   │   └── utils.py
│   ├── db/
│   │   └── database.py
│   ├── repositories/
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── admin.py
│   │   ├── superadmin.py
│   │   ├── posts.py
│   │   ├── users.py
│   │   └── ai.py
│   ├── services/
│   │   └── email.py
│   ├── ai/
│   │   └── event_fetcher.py
│   ├── integrations/
│   │   └── admin_utils.py
│   └── workers/
│       ├── celery_app.py
│       └── tasks.py
├── frontend/
│   └── index.html
├── tests/
├── main.py
├── database.py
├── utils.py
├── services.py
├── event_fetcher.py
├── admin_utils.py
├── celery_app.py
├── tasks.py
├── logger.py
├── index.html
├── requirements.txt
├── .env.example
└── .gitignore
```

## Compatibility wrappers

The root files `database.py`, `utils.py`, `services.py`, `event_fetcher.py`,
`admin_utils.py`, `celery_app.py`, `tasks.py`, and `logger.py` are intentionally kept
as small compatibility wrappers.

This allows existing commands and imports to continue working while the actual implementation
lives under `app/`.

The root `main.py` exposes `app` from `app.main`, so the existing command still works:

```powershell
uvicorn main:app --reload
```

## Preserved API paths

The refactor keeps the existing route paths, including:

- `/auth/*`
- `/platforms/*`
- `/media/upload`
- `/user/profile`
- `/posts/*`
- `/templates/*`
- `/approvals/*`
- `/analytics`
- `/calendar`
- `/ai/*`
- `/admin/*`
- `/superadmin/*`
- `/notifications/*`

The `/posts/upcoming` route is registered before `/posts/{post_id}` so the static
`upcoming` route is not captured by the dynamic post ID route.

## Structural fixes included

1. `main.py` is now a thin entry point.
2. API routes are split by responsibility.
3. Pydantic request models are separated into `app/schemas/`.
4. Authentication/authorization dependencies are centralized.
5. Database implementation is moved to `app/db/database.py`.
6. AI/event/RAG logic is moved to `app/ai/event_fetcher.py`.
7. Celery code is moved to `app/workers/`.
8. Email code is moved to `app/services/email.py`.
9. Configuration is centralized in `app/core/config.py`.
10. The existing CORS environment variable is now actually used instead of being calculated and ignored.
11. Celery worker database initialization is moved out of module import time and into the worker process initialization signal.
12. Runtime Celery Beat files are ignored by Git.
13. Existing `print()` calls touched during the refactor were changed to logging where appropriate.
14. The existing database implementation remains raw SQL for now; repository migration is intentionally a later phase.

## Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create `.env` from `.env.example`.

Start API:

```powershell
uvicorn main:app --reload
```

Start Celery worker:

```powershell
celery -A celery_app.celery_app worker --loglevel=info
```

Start Celery Beat:

```powershell
celery -A celery_app.celery_app beat --loglevel=info
```

## Refactoring rule

After each module is moved:

1. Compile the project.
2. Start FastAPI.
3. Verify Swagger routes.
4. Test the affected API.
5. Commit the change.
6. Only then move to the next module.

Do not migrate the entire database layer to SQLAlchemy/Alembic in the same commit.
