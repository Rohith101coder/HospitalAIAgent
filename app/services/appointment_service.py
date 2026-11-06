import secrets
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.doctor import Doctor
from app.models.slot import DoctorSlot
from app.models.patient import Patient
from app.models.booking_request import BookingRequest
from app.models.appointment import Appointment
from app.models.appointment_history import AppointmentHistory
from app.schemas.appointment import (
    BookingInitiateRequest,
    BookingInitiateResponse,
    AppointmentResponse
)
from app.services.otp_service import OTPService
from app.services.patient_service import PatientService
from app.services.email_service import EmailService
from app.utils.reference_generator import generate_appointment_reference
from app.utils.datetime_utils import (
    now_utc,
    format_slot_time,
    format_date_str
)


class AppointmentService:

    @staticmethod
    def get_available_slots(db: Session, doctor_id: int, target_date: date) -> List[Dict[str, Any]]:
        """Find strictly available future slots for a doctor on a local date."""
        from app.services.slot_service import SlotService
        return SlotService.get_slots_by_doctor_and_date(
            db=db,
            doctor_id=doctor_id,
            target_date=target_date,
            available_only=True
        )

    @staticmethod
    def initiate_booking(
        db: Session,
        data: BookingInitiateRequest
    ) -> Dict[str, Any]:
        """
        Step 1 of Guest Booking:
        Validates doctor and slot, creates a temporary pending BookingRequest,
        and triggers a 6-digit email OTP. Does NOT reserve the slot or confirm booking.
        """
        clean_email = data.patient_email.lower().strip()
        clean_name = data.patient_name.strip()
        clean_phone = data.patient_phone.strip()

        # 1. Validate doctor
        doctor = db.query(Doctor).filter(Doctor.id == data.doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        if not doctor.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is not currently active")

        # 2. Validate slot
        slot = db.query(DoctorSlot).filter(DoctorSlot.id == data.slot_id).first()
        if not slot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        if slot.doctor_id != doctor.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slot does not belong to the selected doctor")
        if slot.status != "available":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected slot is no longer available. Please choose another time.")
        if slot.start_time <= now_utc():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book an appointment slot in the past")

        # 3. Generate unique unguessable booking request reference
        b_ref = "BREQ-" + secrets.token_hex(6).upper()
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=15)

        booking_req = BookingRequest(
            reference=b_ref,
            patient_name=clean_name,
            normalized_email=clean_email,
            phone=clean_phone,
            doctor_id=doctor.id,
            slot_id=slot.id,
            appointment_reason=data.reason,
            status="pending_otp",
            expires_at=expires_at,
            created_at=now
        )
        db.add(booking_req)
        db.commit()
        db.refresh(booking_req)

        # 4. Trigger initial booking OTP dispatch
        OTPService.request_booking_otp(
            db=db,
            booking_request_reference=booking_req.reference,
            patient_email=clean_email
        )

        slot_date = format_date_str(slot.start_time)
        slot_time = format_slot_time(slot.start_time, slot.end_time)

        return {
            "booking_request_reference": booking_req.reference,
            "doctor_name": doctor.name,
            "appointment_date": slot_date,
            "appointment_time": slot_time,
            "patient_email": clean_email,
            "message": f"Verification code sent to {clean_email}. Please provide the 6-digit OTP code to complete your booking."
        }

    @staticmethod
    def confirm_booking(
        db: Session,
        booking_request_reference: str,
        verification_token: Optional[str] = None
    ) -> Appointment:
        """
        Finalize booking:
        Enforces server-side OTP verification of the booking request, revalidates slot
        availability atomically, creates/reuses patient contact record, creates appointment,
        marks booking request completed, and sends confirmation email.
        """
        clean_ref = booking_request_reference.strip().upper()

        booking_req = db.query(BookingRequest).filter(BookingRequest.reference == clean_ref).first()
        if not booking_req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking request reference not found."
            )

        now = datetime.utcnow()
        if now > booking_req.expires_at:
            booking_req.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking request has expired. Please initiate a new booking."
            )

        if booking_req.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking request has already been completed."
            )

        # Optional token verification if caller passes token
        if verification_token:
            is_valid = OTPService.validate_action_authorization(
                token=verification_token,
                expected_purpose="BOOKING",
                booking_request_reference=clean_ref,
                email=booking_req.normalized_email
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired booking verification token."
                )

        # Enforce that server-side OTP verification succeeded for this booking request
        if booking_req.status != "verified":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email OTP verification has not been completed for this booking request."
            )

        slot = db.query(DoctorSlot).filter(DoctorSlot.id == booking_req.slot_id).first()
        if not slot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        if slot.start_time <= now_utc():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book an appointment slot in the past")

        # Atomic reservation of slot
        result = db.execute(
            text("UPDATE doctor_slots SET status = 'booked' WHERE id = :slot_id AND status = 'available'"),
            {"slot_id": slot.id}
        )
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The selected slot is no longer available. Please choose another available slot."
            )

        try:
            # Create or reuse patient contact record
            patient = PatientService.get_or_create_patient(
                db=db,
                full_name=booking_req.patient_name,
                email=booking_req.normalized_email,
                phone=booking_req.phone
            )

            # Generate unique appointment reference
            reference = generate_appointment_reference()
            while db.query(Appointment).filter(Appointment.reference == reference).first() is not None:
                reference = generate_appointment_reference()

            # Create appointment
            appointment = Appointment(
                reference=reference,
                patient_id=patient.id,
                doctor_id=booking_req.doctor_id,
                slot_id=slot.id,
                status="booked",
                reason=booking_req.appointment_reason
            )
            db.add(appointment)
            db.flush()

            # Record history
            history = AppointmentHistory(
                appointment_id=appointment.id,
                old_slot_id=None,
                new_slot_id=slot.id,
                action="booked",
                changed_by="patient"
            )
            db.add(history)

            # Mark booking request completed to prevent reuse
            booking_req.status = "completed"

            db.commit()
            db.refresh(appointment)

            # Send confirmation email
            EmailService.send_booking_confirmation(db=db, appointment=appointment)

            return appointment

        except Exception as e:
            db.rollback()
            try:
                db.execute(
                    text("UPDATE doctor_slots SET status = 'available' WHERE id = :slot_id"),
                    {"slot_id": slot.id}
                )
                db.commit()
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Booking confirmation failed: {str(e)}")

    @staticmethod
    def get_verified_appointments(
        db: Session,
        patient_email: str,
        verification_token: str
    ) -> List[Appointment]:
        """
        Retrieve all appointments for a patient after successful email OTP verification.
        Requires valid signed token with purpose 'VIEW_APPOINTMENTS'.
        """
        clean_email = patient_email.lower().strip()
        is_authorized = OTPService.validate_action_authorization(
            token=verification_token,
            expected_purpose="VIEW_APPOINTMENTS",
            email=clean_email
        )
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authorization token for viewing appointments."
            )

        patient = PatientService.get_patient_by_email(db, clean_email)
        if not patient:
            return []

        return (
            db.query(Appointment)
            .filter(Appointment.patient_id == patient.id)
            .order_by(Appointment.created_at.desc())
            .all()
        )

    @staticmethod
    def get_appointment_by_reference(
        db: Session,
        reference: str,
        verification_token: Optional[str] = None,
        is_admin: bool = False
    ) -> Appointment:
        """
        Find appointment by unique reference code.
        Protects patient privacy: requires admin authorization or verified patient token.
        """
        clean_ref = reference.strip().upper()
        appointment = db.query(Appointment).filter(Appointment.reference == clean_ref).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {reference} not found")

        if not is_admin:
            if not verification_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization is required to view appointment details."
                )
            # Verify token belongs to this reference or patient email
            patient = appointment.patient
            registered_email = patient.normalized_email if (patient and patient.normalized_email) else (patient.email if patient else "")
            from app.core.security import decode_access_token
            payload = decode_access_token(verification_token)
            if not payload or payload.get("type") != "otp_authorization":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid verification token."
                )
            if payload.get("reference") != clean_ref and payload.get("sub") != registered_email:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for this appointment reference."
                )

        return appointment

    @staticmethod
    def get_appointments_list(
        db: Session,
        status_filter: Optional[str] = None,
        doctor_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Appointment]:
        """Admin list of appointments with optional filters."""
        query = db.query(Appointment)
        if status_filter:
            query = query.filter(Appointment.status == status_filter)
        if doctor_id:
            query = query.filter(Appointment.doctor_id == doctor_id)
        return query.order_by(Appointment.created_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def cancel_appointment(
        db: Session,
        reference: str,
        verification_token: Optional[str] = None,
        reason: Optional[str] = None,
        changed_by: str = "patient"
    ) -> Appointment:
        """
        Cancel an active appointment, release its slot, log history, and dispatch email.
        Enforces OTP verification token when requested by patient.
        """
        clean_ref = reference.strip().upper()

        if changed_by != "admin":
            if not verification_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification token is required to cancel an appointment."
                )
            is_valid = OTPService.validate_action_authorization(
                token=verification_token,
                expected_purpose="CANCEL",
                reference=clean_ref
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired cancellation authorization token."
                )

        appointment = db.query(Appointment).filter(Appointment.reference == clean_ref).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {reference} not found")

        if appointment.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment is already cancelled"
            )
        if appointment.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a completed appointment"
            )

        old_slot_id = appointment.slot_id

        try:
            # 1. Release slot if allocated
            if old_slot_id:
                db.execute(
                    text("UPDATE doctor_slots SET status = 'available' WHERE id = :old_slot_id"),
                    {"old_slot_id": old_slot_id}
                )

            # 2. Update appointment
            appointment.status = "cancelled"
            appointment.slot_id = None
            if reason:
                appointment.reason = f"{appointment.reason or ''} [Cancelled: {reason}]".strip()

            # 3. History
            history = AppointmentHistory(
                appointment_id=appointment.id,
                old_slot_id=old_slot_id,
                new_slot_id=None,
                action="cancelled",
                changed_by=changed_by
            )
            db.add(history)

            db.commit()
            db.refresh(appointment)

            EmailService.send_cancellation_confirmation(db=db, appointment=appointment)
            return appointment

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Cancellation failed: {str(e)}")

    @staticmethod
    def reschedule_appointment(
        db: Session,
        reference: str,
        new_slot_id: int,
        verification_token: Optional[str] = None,
        changed_by: str = "patient"
    ) -> Appointment:
        """
        Atomically reschedule an appointment to a new slot.
        Releases old slot and reserves new slot in a single transaction.
        Enforces OTP verification token when requested by patient.
        """
        clean_ref = reference.strip().upper()

        if changed_by != "admin":
            if not verification_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification token is required to reschedule an appointment."
                )
            is_valid = OTPService.validate_action_authorization(
                token=verification_token,
                expected_purpose="RESCHEDULE",
                reference=clean_ref
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired rescheduling authorization token."
                )

        appointment = db.query(Appointment).filter(Appointment.reference == clean_ref).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {reference} not found")

        if appointment.status in ["cancelled", "completed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reschedule an appointment in '{appointment.status}' status"
            )

        new_slot = db.query(DoctorSlot).filter(DoctorSlot.id == new_slot_id).first()
        if not new_slot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New slot not found")
        if new_slot.doctor_id != appointment.doctor_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New slot must belong to the same doctor")
        if new_slot.start_time <= now_utc():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reschedule to a past slot")
        if new_slot.id == appointment.slot_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is already booked for this slot")

        old_slot = appointment.slot
        old_date_str = format_date_str(old_slot.start_time) if old_slot else None
        old_time_str = format_slot_time(old_slot.start_time, old_slot.end_time) if old_slot else None
        old_slot_id = appointment.slot_id

        # Atomic reservation of new slot
        res = db.execute(
            text("UPDATE doctor_slots SET status = 'booked' WHERE id = :new_slot_id AND status = 'available'"),
            {"new_slot_id": new_slot_id}
        )
        if res.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The requested new slot is not available. Original appointment remains unchanged."
            )

        try:
            # Release old slot
            if old_slot_id:
                db.execute(
                    text("UPDATE doctor_slots SET status = 'available' WHERE id = :old_slot_id"),
                    {"old_slot_id": old_slot_id}
                )

            # Update appointment
            appointment.slot_id = new_slot.id
            appointment.status = "booked"

            # History
            history = AppointmentHistory(
                appointment_id=appointment.id,
                old_slot_id=old_slot_id,
                new_slot_id=new_slot.id,
                action="rescheduled",
                changed_by=changed_by
            )
            db.add(history)

            db.commit()
            db.refresh(appointment)

            EmailService.send_rescheduling_confirmation(
                db=db,
                appointment=appointment,
                old_date_str=old_date_str,
                old_time_str=old_time_str
            )

            return appointment

        except Exception as e:
            db.rollback()
            try:
                db.execute(
                    text("UPDATE doctor_slots SET status = 'available' WHERE id = :new_slot_id"),
                    {"new_slot_id": new_slot_id}
                )
                db.commit()
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Rescheduling failed: {str(e)}")

    @staticmethod
    def to_appointment_response(appt: Appointment) -> AppointmentResponse:
        """Helper to format Appointment model to AppointmentResponse schema."""
        slot = appt.slot
        slot_start = slot.start_time if slot else None
        slot_end = slot.end_time if slot else None

        display_date = format_date_str(slot_start) if slot_start else None
        display_time = format_slot_time(slot_start, slot_end) if (slot_start and slot_end) else None

        patient = appt.patient
        patient_email = patient.normalized_email if (patient and patient.normalized_email) else (patient.email if patient else None)

        return AppointmentResponse(
            id=appt.id,
            reference=appt.reference,
            patient_id=appt.patient_id,
            patient_name=patient.full_name if patient else None,
            patient_email=patient_email,
            patient_phone=patient.phone if patient else None,
            doctor_id=appt.doctor_id,
            doctor_name=appt.doctor.name if appt.doctor else None,
            specialty_name=appt.doctor.specialty.name if (appt.doctor and appt.doctor.specialty) else None,
            slot_id=appt.slot_id,
            slot_start_time=slot_start,
            slot_end_time=slot_end,
            display_date=display_date,
            display_time=display_time,
            status=appt.status,
            reason=appt.reason,
            created_at=appt.created_at,
            updated_at=appt.updated_at
        )
