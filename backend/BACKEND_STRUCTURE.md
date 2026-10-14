# Backend structure and current implementation

- `app/main.py`: REST endpoints and WebSocket event handling (existing public entry point retained).
- `app/auth.py`: short-lived HS256 JWT issue/verification using Python standard library; token is bound to player ID and room code.
- `app/config.py`: environment-backed settings, including `SECRET_KEY`.
- `app/database.py`, `app/models.py`, `app/schemas.py`: SQLAlchemy database, persisted entities, and request/response models.
- `app/game.py`: live room state, round countdown, scoring, and round transitions.
- `alembic/`: migration configuration.
- `tests/test_auth.py`: JWT binding/verification tests.
- `tests/test_api.py`: REST API smoke tests.
- `tests/test_scoring.py`: scoring tests.
- `tests/test_websocket.py`: rejects unauthenticated socket connections and checks authenticated lobby connections.

The `core/`, `routers/`, `services/`, `repositories/`, and `websockets/` directories are reserved for future modular extraction; current working routes and game logic remain in `main.py` and `game.py` to preserve the existing import path. See `REQUIREMENTS_AUDIT.md` for requirements that still need end-to-end validation.
