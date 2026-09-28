# Repositories

The first refactoring phase keeps the existing raw SQL implementation in `app/db/database.py`
so behavior is not changed while the application is modularized.

Repositories can be introduced incrementally after each API module is verified.
Do not migrate the whole database layer in one change.
