def test_stateless_chat_basic(client):
    response = client.post(
        "/api/chat",
        json={"message": "Hello, can you help me find a doctor?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert data["is_emergency"] is False
    # Verify no session ID returned
    assert "session_id" not in data


def test_stateless_chat_with_history(client):
    history = [
        {"role": "user", "content": "I am looking for a cardiologist."},
        {"role": "assistant", "content": "We have Dr. Sarah Jenkins and Dr. Rajesh Rao available in Cardiology."}
    ]
    response = client.post(
        "/api/chat",
        json={
            "message": "What are Dr. Sarah Jenkins's consultation hours?",
            "history": history
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert data["is_emergency"] is False


def test_chat_emergency_diverts_immediately(client):
    response = client.post(
        "/api/chat",
        json={"message": "I have severe chest pain and cannot breathe"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_emergency"] is True
    assert "EMERGENCY" in data["reply"]


def test_chat_multilingual_request(client):
    # Telugu transliteration
    r = client.post(
        "/api/chat",
        json={"message": "Naaku doctor appointment kavali, cardiologist unnara?"}
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["reply"]) > 0


def test_old_session_endpoints_removed(client):
    r1 = client.post("/api/chat/session")
    assert r1.status_code in [404, 405]

    r2 = client.get("/api/chat/history/1")
    assert r2.status_code == 404
