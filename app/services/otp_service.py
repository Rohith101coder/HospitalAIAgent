import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.security import (
    generate_secure_otp,
    hash_otp,
    verify_otp_hash,
    create_access_token,
    decode_access_token
)
from app.models.appointment import Appointment
from app.models.booking_request import BookingRequest
from app.models.otp import OTPVerification
from app.services.email_service import EmailService
from app.utils.datetime_utils import format_slot_time, format_date_str


class OTPService:

    @staticmethod
    def request_booking_otp(
        db: Session,
        booking_request_reference: str,
        patient_email: str
    ) -> OTPVerification:
        """
        Generate and dispatch OTP for a pending booking request.
        Enforces 60-second cooldown per email/booking request.
        """
        clean_email = patient_email.strip().lower()
        clean_ref = booking_request_reference.strip().upper()

        booking_req = db.query(BookingRequest).filter(BookingRequest.reference == clean_ref).first()
        if not booking_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking request reference not found"
            )

        if booking_req.normalized_email != clean_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address does not match the booking request"
            )

        now = datetime.utcnow()
        if now > booking_req.expires_at or booking_req.status in ["completed", "expired"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking request has expired or was already completed. Please initiate a new booking."
            )

        # Check cooldown
        last_otp = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.patient_email == clean_email,
                OTPVerification.purpose.in_(["BOOKING", "booking"])
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        if last_otp:
            elapsed = (now - last_otp.created_at).total_seconds()
            if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {remaining} seconds before requesting a new OTP."
                )

        # Invalidate previous unused OTPs for this booking request
        db.query(OTPVerification).filter(
            OTPVerification.booking_request_id == booking_req.id,
            OTPVerification.is_used == False
        ).update({"is_used": True})

        plain_otp = generate_secure_otp(length=6)
        hashed_otp = hash_otp(plain_otp)
        expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        otp_record = OTPVerification(
            patient_email=clean_email,
            otp_hash=hashed_otp,
            purpose="BOOKING",
            booking_request_id=booking_req.id,
            booking_request_reference=booking_req.reference,
            expires_at=expires_at,
            is_used=False,
            failed_attempts=0,
            created_at=now
        )
        db.add(otp_record)
        db.commit()
        db.refresh(otp_record)

        slot = booking_req.slot
        slot_date = format_date_str(slot.start_time) if slot else ""
        slot_time = format_slot_time(slot.start_time, slot.end_time) if slot else ""

        EmailService.send_booking_otp(
            db=db,
            to_email=clean_email,
            patient_name=booking_req.patient_name,
            doctor_name=booking_req.doctor.name if booking_req.doctor else "Doctor",
            appointment_date=slot_date,
            appointment_time=slot_time,
            otp=plain_otp
        )

        return otp_record

    @staticmethod
    def request_lookup_otp(
        db: Session,
        patient_email: str
    ) -> OTPVerification:
        """
        Generate and dispatch OTP for viewing existing appointments without login.
        """
        clean_email = patient_email.strip().lower()
        now = datetime.utcnow()

        # Check cooldown
        last_otp = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.patient_email == clean_email,
                OTPVerification.purpose.in_(["VIEW_APPOINTMENTS", "view_appointments", "VIEW", "view"])
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        if last_otp:
            elapsed = (now - last_otp.created_at).total_seconds()
            if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {remaining} seconds before requesting a new OTP."
                )

        # Invalidate previous unused lookup OTPs for this email
        db.query(OTPVerification).filter(
            OTPVerification.patient_email == clean_email,
            OTPVerification.purpose.in_(["VIEW_APPOINTMENTS", "view_appointments"]),
            OTPVerification.is_used == False
        ).update({"is_used": True})

        plain_otp = generate_secure_otp(length=6)
        hashed_otp = hash_otp(plain_otp)
        expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        otp_record = OTPVerification(
            patient_email=clean_email,
            otp_hash=hashed_otp,
            purpose="VIEW_APPOINTMENTS",
            expires_at=expires_at,
            is_used=False,
            failed_attempts=0,
            created_at=now
        )
        db.add(otp_record)
        db.commit()
        db.refresh(otp_record)

        EmailService.send_lookup_otp(
            db=db,
            to_email=clean_email,
            otp=plain_otp
        )

        return otp_record

    @staticmethod
    def request_appointment_otp(
        db: Session,
        reference: str,
        patient_email: str,
        purpose: str
    ) -> OTPVerification:
        """
        Generate and dispatch OTP for appointment cancellation or rescheduling.
        Enforces appointment reference existence and patient email match.
        """
        clean_email = patient_email.strip().lower()
        clean_ref = reference.strip().upper()
        norm_purpose = purpose.upper()

        if norm_purpose not in ["CANCEL", "RESCHEDULE"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Purpose must be either 'CANCEL' or 'RESCHEDULE'"
            )

        appointment = db.query(Appointment).filter(Appointment.reference == clean_ref).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment reference not found"
            )

        patient = appointment.patient
        registered_email = patient.normalized_email if (patient and patient.normalized_email) else (patient.email if patient else "")
        if registered_email.lower().strip() != clean_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address does not match the registered appointment contact"
            )

        now = datetime.utcnow()
        last_otp = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.appointment_id == appointment.id,
                OTPVerification.purpose.in_([norm_purpose, norm_purpose.lower()])
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        if last_otp:
            elapsed = (now - last_otp.created_at).total_seconds()
            if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {remaining} seconds before requesting a new OTP."
                )

        # Invalidate previous unused OTPs for this appointment and purpose
        db.query(OTPVerification).filter(
            OTPVerification.appointment_id == appointment.id,
            OTPVerification.purpose.in_([norm_purpose, norm_purpose.lower()]),
            OTPVerification.is_used == False
        ).update({"is_used": True})

        plain_otp = generate_secure_otp(length=6)
        hashed_otp = hash_otp(plain_otp)
        expires_at = now + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        otp_record = OTPVerification(
            patient_email=clean_email,
            otp_hash=hashed_otp,
            purpose=norm_purpose,
            appointment_id=appointment.id,
            expires_at=expires_at,
            is_used=False,
            failed_attempts=0,
            created_at=now
        )
        db.add(otp_record)
        db.commit()
        db.refresh(otp_record)

        EmailService.send_otp_email(
            db=db,
            recipient_email=clean_email,
            otp=plain_otp,
            purpose=norm_purpose,
            appointment=appointment
        )

        return otp_record

    @staticmethod
    def request_otp(
        db: Session,
        *args,
        **kwargs
    ) -> OTPVerification:
        """
        Unified polymorphic entry point for requesting OTPs.
        """
        patient_email = kwargs.get("patient_email")
        purpose = kwargs.get("purpose")
        booking_request_reference = kwargs.get("booking_request_reference")
        reference = kwargs.get("reference")

        if args:
            if len(args) >= 3 and "@" in str(args[1]):
                reference = str(args[0])
                patient_email = str(args[1])
                purpose = str(args[2])
            elif len(args) >= 2 and "@" in str(args[0]):
                patient_email = str(args[0])
                purpose = str(args[1])
                if len(args) >= 3:
                    reference = str(args[2])

        if not purpose:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Purpose is required")

        norm_purpose = purpose.upper()

        if norm_purpose == "BOOKING":
            ref = booking_request_reference or reference
            if not ref or not patient_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="booking_request_reference and patient_email are required for booking OTP"
                )
            return OTPService.request_booking_otp(
                db=db,
                booking_request_reference=ref,
                patient_email=patient_email
            )
        elif norm_purpose in ["VIEW_APPOINTMENTS", "VIEW"]:
            if not patient_email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_email is required")
            return OTPService.request_lookup_otp(
                db=db,
                patient_email=patient_email
            )
        elif norm_purpose in ["CANCEL", "RESCHEDULE"]:
            if not reference or not patient_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Appointment reference and patient_email are required for {purpose}"
                )
            return OTPService.request_appointment_otp(
                db=db,
                reference=reference,
                patient_email=patient_email,
                purpose=norm_purpose
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OTP purpose: {purpose}. Supported: BOOKING, VIEW_APPOINTMENTS, CANCEL, RESCHEDULE"
            )

    @staticmethod
    def verify_otp(
        db: Session,
        *args,
        **kwargs
    ) -> str:
        """
        Validate submitted OTP and issue a signed verification JWT token.
        Marks OTP used and updates booking request status to verified when purpose is BOOKING.
        """
        patient_email = kwargs.get("patient_email")
        submitted_otp = kwargs.get("submitted_otp") or kwargs.get("otp")
        purpose = kwargs.get("purpose")
        booking_request_reference = kwargs.get("booking_request_reference")
        reference = kwargs.get("reference")

        if args:
            if len(args) == 4:
                # legacy: (reference, patient_email, submitted_otp, purpose)
                reference = str(args[0])
                patient_email = str(args[1])
                submitted_otp = str(args[2])
                purpose = str(args[3])
            elif len(args) == 3:
                # (patient_email, submitted_otp, purpose)
                patient_email = str(args[0])
                submitted_otp = str(args[1])
                purpose = str(args[2])

        if not patient_email or not submitted_otp or not purpose:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_email, submitted_otp, and purpose are required."
            )

        clean_email = str(patient_email).strip().lower()
        norm_purpose = str(purpose).upper()

        query = db.query(OTPVerification).filter(
            OTPVerification.patient_email == clean_email,
            OTPVerification.purpose.in_([norm_purpose, norm_purpose.lower()]),
            OTPVerification.is_used == False
        )

        appointment = None
        booking_req = None

        if norm_purpose == "BOOKING":
            ref = booking_request_reference or reference
            if ref:
                clean_breq = str(ref).strip().upper()
                booking_req = db.query(BookingRequest).filter(BookingRequest.reference == clean_breq).first()
                if booking_req:
                    query = query.filter(OTPVerification.booking_request_id == booking_req.id)
                else:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking request not found")

        elif reference:
            clean_ref = str(reference).strip().upper()
            appointment = db.query(Appointment).filter(Appointment.reference == clean_ref).first()
            if appointment:
                query = query.filter(OTPVerification.appointment_id == appointment.id)
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment reference not found")

        otp_record = query.order_by(OTPVerification.created_at.desc()).first()

        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending verification request found. Please request a new OTP."
            )

        now = datetime.utcnow()

        if otp_record.failed_attempts >= settings.OTP_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum failed attempts exceeded. Please request a new OTP."
            )

        if now > otp_record.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a fresh code."
            )

        is_valid = verify_otp_hash(str(submitted_otp).strip(), otp_record.otp_hash)
        if not is_valid:
            otp_record.failed_attempts += 1
            db.commit()
            remaining = settings.OTP_MAX_ATTEMPTS - otp_record.failed_attempts
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP code. {remaining} attempts remaining."
            )

        # Mark OTP as used
        otp_record.is_used = True

        # If booking OTP, update booking request status to verified
        if norm_purpose == "BOOKING":
            target_breq = booking_req
            if not target_breq and otp_record.booking_request_id:
                target_breq = db.query(BookingRequest).filter(BookingRequest.id == otp_record.booking_request_id).first()
            if target_breq:
                target_breq.status = "verified"

        db.commit()

        # Build signed token
        token_data: Dict[str, Any] = {
            "sub": clean_email,
            "purpose": norm_purpose,
            "type": "otp_authorization"
        }

        if norm_purpose == "BOOKING":
            if booking_req:
                token_data["booking_request_reference"] = booking_req.reference
            elif otp_record.booking_request_reference:
                token_data["booking_request_reference"] = otp_record.booking_request_reference

        if otp_record.appointment_id:
            token_data["appointment_id"] = otp_record.appointment_id
            if appointment:
                token_data["reference"] = appointment.reference
            else:
                appt = db.query(Appointment).filter(Appointment.id == otp_record.appointment_id).first()
                if appt:
                    token_data["reference"] = appt.reference

        verification_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=15)
        )

        return verification_token

    @staticmethod
    def validate_action_authorization(
        token: Optional[str],
        *args,
        **kwargs
    ) -> bool:
        """
        Validate that a caller possesses a valid signed verification token
        for this exact purpose, reference, booking request reference, or email.
        """
        if not token:
            return False

        payload = decode_access_token(token)
        if not payload:
            return False

        if payload.get("type") != "otp_authorization":
            return False

        expected_purpose = kwargs.get("expected_purpose") or kwargs.get("purpose")
        reference = kwargs.get("reference")
        booking_request_reference = kwargs.get("booking_request_reference")
        email = kwargs.get("email")

        if args:
            if len(args) == 2:
                reference = str(args[0])
                expected_purpose = str(args[1])
            elif len(args) == 1:
                expected_purpose = str(args[0])

        if expected_purpose and payload.get("purpose") != expected_purpose.upper():
            return False

        if reference:
            token_ref = payload.get("reference")
            if not token_ref or token_ref.upper() != reference.strip().upper():
                return False

        if booking_request_reference:
            token_bref = payload.get("booking_request_reference")
            if not token_bref or token_bref.upper() != booking_request_reference.strip().upper():
                return False

        if email:
            token_sub = payload.get("sub")
            if not token_sub or token_sub.lower() != email.strip().lower():
                return False

        return True
