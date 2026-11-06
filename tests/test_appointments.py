from datetime import date, timedelta
import pytest
from fastapi import HTTPException
from app.models.slot import DoctorSlot
from app.models.appointment import Appointment
from app.models.appointment_history import AppointmentHistory
from app.models.otp import OTPVerification
from app.services.appointment_service import AppointmentService
from app.services.otp_service import OTPService
from app.schemas.appointment import BookingInitiateRequest
from app.core.security import hash_otp


def test_direct_booking_endpoint_removed(client, db_session):
    """Verify that old POST /api/appointments direct booking bypass is completely removed."""
    slot = db_session.query(DoctorSlot).filter(DoctorSlot.status == "available").first()
    assert slot is not None

    booking_data = {
        "patient_name": "Bypass Attempt Patient",
        "patient_email": "bypass@example.com",
        "patient_phone": "+919876543210",
        "doctor_id": slot.doctor_id,
        "slot_id": slot.id,
        "reason": "Direct booking attempt"
    }

    resp = client.post("/api/appointments", json=booking_data)
    # Direct endpoint does not exist; only admin GET /api/appointments exists on base route
    assert resp.status_code in [404, 405]


def test_guest_booking_flow_complete(client, db_session):
    """
    Test complete patient guest booking workflow:
    1. Initiate booking -> sends OTP and returns booking_request_reference
    2. Verify OTP -> marks booking request verified
    3. Confirm booking -> atomically reserves slot and creates appointment
    """
    slot = db_session.query(DoctorSlot).filter(DoctorSlot.status == "available").first()
    assert slot is not None

    patient_email = "guest.test@example.com"
    initiate_data = {
        "doctor_id": slot.doctor_id,
        "slot_id": slot.id,
        "patient_name": "Guest Patient",
        "patient_phone": "+919876543210",
        "patient_email": patient_email,
        "reason": "Routine Cardiology Consultation"
    }

    # Step 1: Initiate booking
    initiate_resp = client.post("/api/appointments/initiate", json=initiate_data)
    assert initiate_resp.status_code == 200
    init_data = initiate_resp.json()
    b_ref = init_data["booking_request_reference"]
    assert b_ref.startswith("BREQ-")

    # Step 2: Set known test OTP in database
    db_session.commit()
    otp_record = (
        db_session.query(OTPVerification)
        .filter(
            OTPVerification.booking_request_reference == b_ref,
            OTPVerification.purpose.in_(["BOOKING", "booking"])
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )
    assert otp_record is not None
    test_otp = "123456"
    otp_record.otp_hash = hash_otp(test_otp)
    db_session.commit()

    # Step 3: Verify OTP
    verify_resp = client.post(
        "/api/appointments/verify-otp",
        json={
            "patient_email": patient_email,
            "otp": test_otp,
            "purpose": "BOOKING",
            "booking_request_reference": b_ref
        }
    )
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    token = v_data["verification_token"]
    assert token is not None

    # Step 4: Confirm booking
    confirm_resp = client.post(
        "/api/appointments/confirm",
        json={
            "booking_request_reference": b_ref,
            "verification_token": token
        }
    )
    assert confirm_resp.status_code == 201
    confirm_data = confirm_resp.json()
    assert confirm_data["reference"].startswith("MED-")
    assert confirm_data["status"] == "booked"
    assert confirm_data["doctor_id"] == slot.doctor_id

    # Verify slot is booked in DB
    db_session.commit()
    updated_slot = db_session.query(DoctorSlot).filter(DoctorSlot.id == slot.id).first()
    assert updated_slot.status == "booked"

    # Verify history recorded
    appt = db_session.query(Appointment).filter(Appointment.reference == confirm_data["reference"]).first()
    assert appt is not None
    history = db_session.query(AppointmentHistory).filter(AppointmentHistory.appointment_id == appt.id).first()
    assert history is not None
    assert history.action == "booked"


def test_reject_booking_unavailable_slot(client, db_session):
    booked_slot = db_session.query(DoctorSlot).filter(DoctorSlot.status == "booked").first()
    assert booked_slot is not None

    initiate_data = {
        "doctor_id": booked_slot.doctor_id,
        "slot_id": booked_slot.id,
        "patient_name": "Another Patient",
        "patient_phone": "+919876543211",
        "patient_email": "another@example.com",
        "reason": "Duplicate attempt"
    }

    resp = client.post("/api/appointments/initiate", json=initiate_data)
    assert resp.status_code == 409


def test_reject_slot_belonging_to_another_doctor(client, db_session):
    slots = db_session.query(DoctorSlot).filter(DoctorSlot.status == "available").all()
    slot = slots[0]
    wrong_doctor_id = slot.doctor_id + 999

    initiate_data = {
        "doctor_id": wrong_doctor_id,
        "slot_id": slot.id,
        "patient_name": "Mismatch Patient",
        "patient_phone": "+919876543212",
        "patient_email": "mismatch@example.com"
    }

    resp = client.post("/api/appointments/initiate", json=initiate_data)
    assert resp.status_code in [400, 404]


def test_cancel_and_reschedule_service(db_session):
    slot1 = db_session.query(DoctorSlot).filter(DoctorSlot.status == "available").first()
    patient_email = "lifecycle.svc@example.com"

    # 1. Initiate booking
    init_res = AppointmentService.initiate_booking(
        db=db_session,
        data=BookingInitiateRequest(
            patient_name="Lifecycle Patient",
            patient_email=patient_email,
            patient_phone="+919876543299",
            doctor_id=slot1.doctor_id,
            slot_id=slot1.id,
            reason="Testing cancellation & rescheduling"
        )
    )
    b_ref = init_res["booking_request_reference"]

    # 2. Mock OTP verification
    test_otp = "654321"
    otp_record = (
        db_session.query(OTPVerification)
        .filter(OTPVerification.booking_request_reference == b_ref)
        .first()
    )
    otp_record.otp_hash = hash_otp(test_otp)
    db_session.commit()

    token = OTPService.verify_otp(
        db=db_session,
        patient_email=patient_email,
        submitted_otp=test_otp,
        purpose="BOOKING",
        booking_request_reference=b_ref
    )

    # 3. Confirm booking
    appt = AppointmentService.confirm_booking(
        db=db_session,
        booking_request_reference=b_ref,
        verification_token=token
    )
    assert appt.status == "booked"

    # Find another slot for rescheduling
    slot2 = db_session.query(DoctorSlot).filter(
        DoctorSlot.doctor_id == appt.doctor_id,
        DoctorSlot.status == "available",
        DoctorSlot.id != slot1.id
    ).first()
    assert slot2 is not None

    # Reschedule directly via admin authority
    rescheduled = AppointmentService.reschedule_appointment(
        db=db_session,
        reference=appt.reference,
        new_slot_id=slot2.id,
        changed_by="admin"
    )
    assert rescheduled.slot_id == slot2.id
    db_session.refresh(slot1)
    assert slot1.status == "available"
    db_session.refresh(slot2)
    assert slot2.status == "booked"

    # Cancel via admin authority
    cancelled = AppointmentService.cancel_appointment(
        db=db_session,
        reference=appt.reference,
        reason="Admin cancelled",
        changed_by="admin"
    )
    assert cancelled.status == "cancelled"
    assert cancelled.slot_id is None
    db_session.refresh(slot2)
    assert slot2.status == "available"
