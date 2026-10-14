# Requirements audit — current implementation status

This audit distinguishes code present from features verified in a full browser session.

## Implemented in this update
- Player entry endpoints issue short-lived HS256 JWT tokens.
- WebSocket connections require a valid token bound to the requested player ID and room code.
- Tokens are signature-checked and expire after 12 hours.
- Frontend passes the returned token when opening the WebSocket.
- Automated tests cover valid token binding, wrong player/room rejection, missing-token socket rejection, and authenticated socket connection.

## Existing functionality (requires full end-to-end validation)
- Room create/join REST endpoints and room codes.
- Lobby readiness, host start action, drawing stroke events, clear canvas, guesses, score updates, countdown, round changes, and game completion in the live-room engine.
- SQLAlchemy persistence for rooms, players, rounds, and guesses.
- React canvas and lobby/game panels.

## Still needs implementation hardening or verification
- Durable reconnect tokens for players who reconnect after the lobby closes; currently token refresh is available through join only while the room is in lobby state.
- Strict host identity persistence and authorization for REST endpoints beyond the WebSocket session.
- Robust multi-worker/multi-container room coordination (current live room state is process-local).
- Reconnection state replay and drawing-operation replay for clients that reconnect mid-round.
- Prevent repeated or malformed guess spam and apply a rate limit.
- Audit all secret-word exposure paths and add tests that the word is delivered only to the drawer.
- Migration-first schema initialization and a tested initial Alembic migration; current app startup calls `create_all`.
- Full two-browser Docker-based end-to-end test, frontend production build, and CI workflow.

## Configuration note
Set a unique, long `SECRET_KEY` in `.env` before deployment. The example value is intentionally a placeholder and must not be used in production. Use HTTPS/WSS for deployed environments.
