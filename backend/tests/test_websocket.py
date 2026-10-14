from fastapi.testclient import TestClient
from app.main import app


def test_websocket_connection_requires_token():
    c = TestClient(app)
    created = c.post("/api/rooms", json={"display_name": "WS Tester", "total_rounds": 1}).json()
    # A player ID alone must not be enough to impersonate a player.
    with c.websocket_connect(f"/ws/{created['room_code']}/{created['player_id']}") as ws:
        assert ws.receive_json()["type"] == "error"


def test_websocket_connection_and_lobby_with_valid_token():
    c = TestClient(app)
    created = c.post("/api/rooms", json={"display_name": "WS Tester", "total_rounds": 1}).json()
    assert created["access_token"]
    with c.websocket_connect(
        f"/ws/{created['room_code']}/{created['player_id']}?token={created['access_token']}"
    ) as ws:
        assert ws.receive_json()["type"] == "connection_state"
        assert ws.receive_json()["type"] == "lobby_state"
