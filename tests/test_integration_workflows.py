from datetime import date, timedelta
from app.models.slot import DoctorSlot
from app.models.appointment import Appointment
from app.models.otp import OTPVerification
from app.services.otp_service import OTPService
from app.core.security import hash_otp


def test_health_endpoint(client):
    """Verify health endpoint checks database connectivity."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_full_patient_booking_reschedule_cancellation_lifecycle(client, db_session):
    """
    Complete end-to-end patient workflow:
    1. Search doctors by specialty.
    2. Get available slots.
    3. Book appointment via initiate -> verify OTP -> confirm.
    4. Request OTP for rescheduling.
    5. Submit OTP and receive verification token.
    6. Reschedule appointment to a different slot.
    7. Verify old slot released, new slot booked.
    8. Request OTP for cancellation.
    9. Submit OTP and cancel appointment.
    10. Verify appointment cancelled and slot released.
    """
    # 1. Search doctors
    doc_resp = client.get("/api/doctors/search?specialty=Cardiology")
    assert doc_resp.status_code == 200
    doctors = doc_resp.json()
    assert len(doctors) > 0
    doctor_id = doctors[0]["id"]

    # 2. Get available slots for a date where slots exist
    slots = db_session.query(DoctorSlot).filter(
        DoctorSlot.doctor_id == doctor_id,
        DoctorSlot.status == "available"
    ).all()
    assert len(slots) >= 2
    target_date = slots[0].start_time.strftime("%Y-%m-%d")

    slots_resp = client.get(f"/api/doctors/{doctor_id}/slots?date={target_date}")
    assert slots_resp.status_code == 200
    available_slots = slots_resp.json()
    assert len(available_slots) >= 2
    first_slot = available_slots[0]
    second_slot = available_slots[1]

    # 3. Book appointment via guest OTP flow
    patient_email = "lifecycle.test@example.com"
    booking_payload = {
        "patient_name": "Satish Kumar",
        "patient_email": patient_email,
        "patient_phone": "+919849011223",
        "doctor_id": doctor_id,
        "slot_id": first_slot["id"],
        "reason": "Chest discomfort during morning walks"
    }

    # Step 3a: Initiate
    init_resp = client.post("/api/appointments/initiate", json=booking_payload)
    assert init_resp.status_code == 200
    b_ref = init_resp.json()["booking_request_reference"]

    # Step 3b: Fast-track OTP verification in test
    db_session.commit()
    otp_booking_rec = (
        db_session.query(OTPVerification)
        .filter(OTPVerification.booking_request_reference == b_ref)
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    test_booking_otp = "112233"
    otp_booking_rec.otp_hash = hash_otp(test_booking_otp)
    db_session.commit()

    verify_booking_resp = client.post(
        "/api/appointments/verify-otp",
        json={
            "patient_email": patient_email,
            "otp": test_booking_otp,
            "purpose": "BOOKING",
            "booking_request_reference": b_ref
        }
    )
    assert verify_booking_resp.status_code == 200
    booking_token = verify_booking_resp.json()["verification_token"]

    # Step 3c: Confirm
    book_resp = client.post(
        "/api/appointments/confirm",
        json={
            "booking_request_reference": b_ref,
            "verification_token": booking_token
        }
    )
    assert book_resp.status_code == 201
    booking = book_resp.json()
    reference = booking["reference"]
    assert reference.startswith("MED-")

    # 4. Request OTP for Rescheduling
    otp_req_resp = client.post(
        "/api/appointments/request-otp",
        json={"reference": reference, "patient_email": patient_email, "purpose": "reschedule"}
    )
    assert otp_req_resp.status_code == 200

    # 5. Fast-track OTP verification for reschedule
    db_session.commit()
    test_otp_code = "889900"
    otp_record = (
        db_session.query(OTPVerification)
        .filter(
            OTPVerification.patient_email == patient_email,
            OTPVerification.purpose.in_(["RESCHEDULE", "reschedule"])
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    otp_record.otp_hash = hash_otp(test_otp_code)
    db_session.commit()

    verify_resp = client.post(
        "/api/appointments/verify-otp",
        json={
            "reference": reference,
            "patient_email": patient_email,
            "otp": test_otp_code,
            "purpose": "reschedule"
        }
    )
    assert verify_resp.status_code == 200
    reschedule_token = verify_resp.json()["verification_token"]

    # 6. Reschedule to second_slot
    resched_resp = client.post(
        "/api/appointments/reschedule",
        json={
            "reference": reference,
            "new_slot_id": second_slot["id"],
            "verification_token": reschedule_token
        }
    )
    assert resched_resp.status_code == 200
    resched_data = resched_resp.json()
    assert resched_data["slot_id"] == second_slot["id"]

    # 7. Check database slot states
    db_session.commit()
    s1 = db_session.query(DoctorSlot).filter(DoctorSlot.id == first_slot["id"]).first()
    s2 = db_session.query(DoctorSlot).filter(DoctorSlot.id == second_slot["id"]).first()
    assert s1.status == "available"
    assert s2.status == "booked"

    # 8. Request OTP for Cancellation
    client.post(
        "/api/appointments/request-otp",
        json={"reference": reference, "patient_email": patient_email, "purpose": "cancel"}
    )
    db_session.commit()
    cancel_otp_code = "776655"
    otp_record_cancel = (
        db_session.query(OTPVerification)
        .filter(
            OTPVerification.patient_email == patient_email,
            OTPVerification.purpose.in_(["CANCEL", "cancel"])
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    otp_record_cancel.otp_hash = hash_otp(cancel_otp_code)
    db_session.commit()

    verify_cancel_resp = client.post(
        "/api/appointments/verify-otp",
        json={
            "reference": reference,
            "patient_email": patient_email,
            "otp": cancel_otp_code,
            "purpose": "cancel"
        }
    )
    assert verify_cancel_resp.status_code == 200
    cancel_token = verify_cancel_resp.json()["verification_token"]

    # 9. Cancel appointment
    cancel_resp = client.post(
        "/api/appointments/cancel",
        json={
            "reference": reference,
            "reason": "Personal reasons",
            "verification_token": cancel_token
        }
    )
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == "cancelled"
    assert cancel_data["slot_id"] is None

    # 10. Check slot 2 is released
    db_session.commit()
    s2_updated = db_session.query(DoctorSlot).filter(DoctorSlot.id == second_slot["id"]).first()
    assert s2_updated.status == "available"


def test_guest_booking_with_otp_and_view_appointments(client, db_session):
    """
    Test guest patient workflow:
    1. Initiate booking -> OTP dispatched, booking request created.
    2. Verify OTP -> Token received, booking request marked verified.
    3. Confirm booking -> Slot reserved atomically, Appointment created.
    4. Request OTP to view appointments without login.
    5. Verify OTP -> Token received.
    6. Retrieve appointments -> Verified list displayed.
    """
    slot = db_session.query(DoctorSlot).filter(DoctorSlot.status == "available").first()
    assert slot is not None
    email = "guest.journey@example.com"

    # 1. Initiate booking
    init_payload = {
        "patient_name": "Guest Ramesh",
        "patient_email": email,
        "patient_phone": "+919876543233",
        "doctor_id": slot.doctor_id,
        "slot_id": slot.id,
        "reason": "Consultation checkup"
    }
    init_resp = client.post("/api/appointments/initiate", json=init_payload)
    assert init_resp.status_code == 200
    b_ref = init_resp.json()["booking_request_reference"]
    assert b_ref.startswith("BREQ-")

    # 2. Fast-track OTP in test
    db_session.commit()
    otp_record = (
        db_session.query(OTPVerification)
        .filter(OTPVerification.booking_request_reference == b_ref)
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    otp_record.otp_hash = hash_otp("445566")
    db_session.commit()

    # 3. Verify OTP
    verify_resp = client.post(
        "/api/appointments/verify-otp",
        json={
            "patient_email": email,
            "otp": "445566",
            "purpose": "BOOKING",
            "booking_request_reference": b_ref
        }
    )
    assert verify_resp.status_code == 200
    token = verify_resp.json()["verification_token"]

    # 4. Confirm booking
    confirm_resp = client.post(
        "/api/appointments/confirm",
        json={
            "booking_request_reference": b_ref,
            "verification_token": token
        }
    )
    assert confirm_resp.status_code == 201
    booking_ref = confirm_resp.json()["reference"]
    assert booking_ref.startswith("MED-")

    # 5. Request OTP to view appointments
    lookup_otp_resp = client.post(
        "/api/appointments/request-otp",
        json={"patient_email": email, "purpose": "VIEW_APPOINTMENTS"}
    )
    assert lookup_otp_resp.status_code == 200

    # 6. Set OTP for lookup
    db_session.commit()
    lookup_otp_rec = (
        db_session.query(OTPVerification)
        .filter(
            OTPVerification.patient_email == email,
            OTPVerification.purpose.in_(["VIEW_APPOINTMENTS", "view_appointments"])
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    lookup_otp_rec.otp_hash = hash_otp("778899")
    db_session.commit()

    # 7. Verify OTP for lookup
    lookup_verify_resp = client.post(
        "/api/appointments/verify-otp",
        json={"patient_email": email, "otp": "778899", "purpose": "VIEW_APPOINTMENTS"}
    )
    assert lookup_verify_resp.status_code == 200
    view_token = lookup_verify_resp.json()["verification_token"]

    # 8. View verified appointments
    view_resp = client.get(f"/api/appointments/verified?email={email}&token={view_token}")
    assert view_resp.status_code == 200
    view_data = view_resp.json()
    assert view_data["total"] >= 1
    refs = [a["reference"] for a in view_data["appointments"]]
    assert booking_ref in refs
