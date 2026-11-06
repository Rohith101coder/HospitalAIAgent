def test_admin_stats(client, auth_headers):
    # Without auth
    resp = client.get("/api/admin/stats")
    assert resp.status_code == 401

    # With auth
    resp = client.get("/api/admin/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_appointments" in data
    assert "active_doctors" in data
    assert "active_specialties" in data
    assert data["active_doctors"] >= 6
    assert data["active_specialties"] >= 7


def test_admin_appointments_and_notifications(client, auth_headers):
    # Appointments
    resp = client.get("/api/admin/appointments", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Notifications
    resp = client.get("/api/admin/notifications", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # Handoffs
    resp = client.get("/api/admin/handoffs", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_admin_trigger_reminders(client, auth_headers):
    # Trigger 24h
    r24 = client.post("/api/admin/jobs/run-24h-reminders", headers=auth_headers)
    assert r24.status_code == 200
    assert r24.json()["success"] is True

    # Trigger 2h
    r2 = client.post("/api/admin/jobs/run-2h-reminders", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["success"] is True

    # Trigger all
    r_all = client.post("/api/admin/jobs/run-reminders", headers=auth_headers)
    assert r_all.status_code == 200
    assert r_all.json()["success"] is True

