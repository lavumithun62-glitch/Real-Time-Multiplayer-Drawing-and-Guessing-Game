# Real-Time Multiplayer Drawing & Guessing Game

Full-stack starter implementation: FastAPI + WebSockets + SQLAlchemy/MySQL and React/TypeScript/Vite/Canvas. It includes room creation/joining, lobby readiness, drawing operations, guesses, round rotation, scoring, reconnect support, history/leaderboard/statistics endpoints, Docker Compose, and tests.

## Quick start (Windows / VS Code)
1. Extract the ZIP and open `realtime-drawing-guessing-game` in VS Code.
2. Install and start Docker Desktop.
3. In the VS Code PowerShell terminal run: `Copy-Item .env.example .env`
4. Run: `docker compose up --build` (first build needs internet to download images/packages).
5. Open frontend at http://localhost:5173 and API docs at http://localhost:8000/docs. MySQL is exposed on host port 3307 (container port 3306).
6. Stop with `Ctrl+C`, or `docker compose down`; data is retained in the named volume. Use `docker compose down -v` only if you want to delete database data.

## Local backend tests
From `backend`: `python -m venv .venv`, activate it, `pip install -r requirements.txt`, then `pytest`. For local SQLite tests set `DATABASE_URL=sqlite:///./test.db` in the environment. The application creates tables on startup for ease of local setup; Alembic configuration is included for migration workflows.

## Gameplay
- Create a room and share its 6-character room code. Another player joins with that code.
- Players mark Ready; host can start when at least two players are connected and ready.
- Drawer alone receives the word. Drawing uses vector operations (not canvas screenshots). Guesses, score events, timer ticks, round results and disconnects are broadcast as typed JSON events.
- If the drawer disconnects, the round ends and rotation continues. A reconnect using the same room code and display name reuses that player's identity while the room is active.

## WebSocket protocol
Connect to `/ws/{room_code}/{player_id}`. Client events: `ready` (`{ready:boolean}`), `start_game`, `stroke` (`{x0,y0,x1,y1,color,width,tool}`), `clear_canvas`, `guess` (`{text}`), `leave`. Server events include `lobby_state`, `player_joined`, `player_left`, `player_ready`, `game_started`, `round_started`, `drawer_word` (drawer only), `stroke`, `canvas_cleared`, `guess_result`, `correct_guess`, `scoreboard`, `timer`, `round_ended`, `game_finished`, `error`, and `connection_state`. Never trust client scores or word values; the server computes both.

## REST API
- `POST /api/rooms` create room
- `GET /api/rooms/{room_code}` public room snapshot (never includes secret word)
- `GET /api/history` completed game history
- `GET /api/leaderboard` top players by aggregate persisted score
- `GET /api/players/{player_id}/stats` player statistics
- `GET /health` health check

## Notes / production hardening
The in-memory live room registry is appropriate for a single backend instance. For horizontally scaled deployment, move room state/pub-sub and timers to Redis, add authenticated signed player tokens/rate limiting, and use Alembic migrations as deployment gates. The sample is an educational runnable baseline; use a production secret and review access controls before public deployment.

## Player JWT and WebSocket security

Room creation and joining return a short-lived HS256 JWT in `access_token`. The browser passes it to the WebSocket endpoint as `?token=...` because the browser WebSocket API does not support arbitrary authorization headers. The server validates the signature, expiry, player ID, and room code before accepting the socket. A player ID alone is no longer sufficient to connect.

Set `SECRET_KEY` in `.env` to a long, unique random value before sharing or deploying the application. Never use the example value in production. Since browser WebSocket URLs contain the token, use HTTPS/WSS in deployed environments and avoid logging full WebSocket URLs. Tokens expire after 12 hours; a player can obtain a new token by joining the room again while it is accepting players.
