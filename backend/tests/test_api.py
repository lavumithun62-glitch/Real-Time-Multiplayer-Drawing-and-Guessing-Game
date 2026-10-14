import os
os.environ["DATABASE_URL"]="sqlite:///./test_api.db"
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health():
    assert client.get("/health").json()["status"]=="ok"
def test_create_room_hides_secret():
    r=client.post("/api/rooms",json={"display_name":"Tester","total_rounds":2})
    assert r.status_code==201
    code=r.json()["room_code"]
    room=client.get(f"/api/rooms/{code}").json()
    assert "word" not in room and "secret_word" not in room

def test_create_room_rejects_whitespace_display_name():
    response = client.post("/api/rooms", json={"display_name": "   ", "total_rounds": 1})
    assert response.status_code == 422
