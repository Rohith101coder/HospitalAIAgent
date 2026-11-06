from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from app.models.appointment import Appointment
from app.models.otp import OTPVerification
from app.services.otp_service import OTPService
from app.core.security import generate_secure_otp, hash_otp, create_access_token
from app.models.slot import DoctorSlot
from app.services.appointment_service import AppointmentService


def test_otp_flow_complete(db_session):
    appt = db_session.query(Appointment).filter(Appointment.status != "cancelled").first()
    assert appt is not None
    patient = appt.patient
    email = patient.normalized_email if (patient and patient.normalized_email) else (patient.email if patient else "")

    # Request OTP
    otp_record = OTPService.request_otp(
        db=db_session,
        reference=appt.reference,
        patient_email=email,
        purpose="cancel"
    )
    assert otp_record.appointment_id == appt.id
    assert otp_record.is_used is False

    # For testing, generate known plain OTP and set hash
    test_otp = "123456"
    otp_record.otp_hash = hash_otp(test_otp)
    db_session.commit()

    # Wrong email rejected
    with pytest.raises(HTTPException) as exc:
        OTPService.verify_otp(
            db=db_session,
            reference=appt.reference,
            patient_email="wrong.email@example.com",
            submitted_otp=test_otp,
            purpose="cancel"
        )
    assert exc.value.status_code in [400, 404]

    # Wrong OTP rejected
    with pytest.raises(HTTPException) as exc:
        OTPService.verify_otp(
            db=db_session,
            reference=appt.reference,
            patient_email=email,
            submitted_otp="999999",
            purpose="cancel"
        )
    assert exc.value.status_code == 400

    # Correct OTP verified
    token = OTPService.verify_otp(
        db=db_session,
        reference=appt.reference,
        patient_email=email,
        submitted_otp=test_otp,
        purpose="cancel"
    )
    assert token is not None

    # Token authorizes cancel for this reference
    assert OTPService.validate_action_authorization(token, appt.reference, "cancel") is True

    # Token rejected for different operation
    assert OTPService.validate_action_authorization(token, appt.reference, "reschedule") is False

    # Token rejected for different appointment
    assert OTPService.validate_action_authorization(token, "MED-9999-DIFFERENT", "cancel") is False

    # OTP is marked as used and cannot be reused
    with pytest.raises(HTTPException):
        OTPService.verify_otp(
            db=db_session,
            reference=appt.reference,
            patient_email=email,
            submitted_otp=test_otp,
            purpose="cancel"
        )


def test_otp_expiration_and_attempt_limit(db_session):
    appt = db_session.query(Appointment).filter(Appointment.status != "cancelled").first()
    assert appt is not None
    patient = appt.patient
    email = patient.normalized_email if (patient and patient.normalized_email) else (patient.email if patient else "")

    # Test expired OTP
    expired_otp = OTPVerification(
        patient_email=email,
        otp_hash=hash_otp("654321"),
        purpose="reschedule",
        appointment_id=appt.id,
        expires_at=datetime.utcnow() - timedelta(minutes=1),  # Expired
        is_used=False,
        failed_attempts=0,
        created_at=datetime.utcnow() - timedelta(minutes=6)
    )
    db_session.add(expired_otp)
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        OTPService.verify_otp(
            db=db_session,
            reference=appt.reference,
            patient_email=email,
            submitted_otp="654321",
            purpose="reschedule"
        )
    assert exc.value.status_code == 400
    assert "expired" in exc.value.detail.lower()
