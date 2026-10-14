# Backend hardening progress (2026-10-14)

## Changes in this update
- REST room creation/join validation now trims display names and rejects whitespace-only names.
- WebSocket connect sends a `state_snapshot` event with current round/timer/drawing operations for recovery. The secret word is included only for the active drawer.
- Unexpected WebSocket exceptions are logged with room/player context instead of being silently swallowed.
- Added API validation and JWT player/room binding tests.

## Verification
- `python -m pytest -q`: 10 passed.
- Python compilation: checked for application and test modules.

## Still to finish before calling the backend complete
- Replace startup `Base.metadata.create_all()` with a documented Alembic-first migration workflow.
- Test and harden round-end/disconnect races and persist scores at each authoritative scoring event.
- Ensure room/host identity and readiness policy remain correct after host disconnect/reconnect.
- Add broader WebSocket integration tests for drawer-only word delivery, guessing, drawing authorization, timer expiry, disconnects, and game completion.
- Add DB-backed tests against MySQL, not only SQLite.
- Run a full Docker smoke test and verify reconnect snapshots against the frontend event handler.
