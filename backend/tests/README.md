# Backend test layout

Run from `backend/` with the project virtual environment activated:

```powershell
python -m pytest -q
```

Place pure scoring/round rules in `unit/`, FastAPI TestClient endpoint tests in `api/`, and real WebSocket connect/reconnect/event-flow tests in `integration/`. Existing starter tests remain at the top level and are kept for compatibility.
