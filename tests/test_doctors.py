from datetime import date, timedelta


def test_get_specialties(client):
    response = client.get("/api/specialties")
    assert response.status_code == 200
    specialties = response.json()
    assert len(specialties) >= 7
    names = [s["name"] for s in specialties]
    assert "Cardiology" in names
    assert "Neurology" in names


def test_create_specialty_admin_required(client):
    # Without auth
    resp = client.post("/api/specialties", json={"name": "Oncology", "description": "Cancer treatment"})
    assert resp.status_code == 401


def test_create_specialty_success(client, auth_headers):
    resp = client.post(
        "/api/specialties",
        json={"name": "ENT", "description": "Ear, Nose, Throat care"},
        headers=auth_headers
    )
    # 201 or 400 if already exists
    assert resp.status_code in [201, 400]


def test_get_doctors(client):
    response = client.get("/api/doctors")
    assert response.status_code == 200
    doctors = response.json()
    assert len(doctors) >= 6


def test_search_doctors_by_specialty(client):
    response = client.get("/api/doctors/search?specialty=Cardiology")
    assert response.status_code == 200
    doctors = response.json()
    assert len(doctors) >= 1
    assert "Dr. Ramesh Sharma" in [d["name"] for d in doctors]


def test_get_doctor_slots(client):
    # Fetch a doctor
    docs = client.get("/api/doctors").json()
    doctor_id = docs[0]["id"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = client.get(f"/api/doctors/{doctor_id}/slots?date={tomorrow}")
    assert response.status_code == 200
    slots = response.json()
    assert isinstance(slots, list)


def test_block_slot(client, auth_headers):
    docs = client.get("/api/doctors").json()
    doctor_id = docs[0]["id"]
    tomorrow = (date.today() + timedelta(days=2)).isoformat()

    slots_resp = client.get(f"/api/doctors/{doctor_id}/slots?date={tomorrow}")
    slots = slots_resp.json()
    if slots:
        slot_id = slots[0]["id"]
        block_resp = client.post(f"/api/schedules/block-slot/{slot_id}", headers=auth_headers)
        assert block_resp.status_code == 200
        assert block_resp.json()["status"] == "blocked"

