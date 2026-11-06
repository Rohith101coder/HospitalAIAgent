import os
from datetime import datetime
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.notification import Notification
from app.models.appointment import Appointment
from app.utils.datetime_utils import format_slot_time, format_date_str

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "emails")


def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Simple template renderer replacing {{ variable }} placeholders."""
    template_path = os.path.join(TEMPLATES_DIR, template_name)
    if not os.path.exists(template_path):
        return f"<p>{context}</p>"

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Include default system contacts
    full_context = {
        "emergency_number": settings.EMERGENCY_NUMBER,
        "front_desk_email": settings.FRONT_DESK_EMAIL,
        "expiry_minutes": settings.OTP_EXPIRY_MINUTES,
        **context
    }

    # Render simple {{ key }} substitutions
    for k, v in full_context.items():
        placeholder = f"{{{{ {k} }}}}"
        content = content.replace(placeholder, str(v) if v is not None else "")

    return content


class EmailService:

    @staticmethod
    def send_email(
        db: Session,
        to_email: str,
        to_name: str,
        subject: str,
        html_content: str,
        notification_type: str,
        appointment_id: Optional[int] = None
    ) -> bool:
        """
        Send transactional email via Brevo API and log in notifications table.
        Safe against network or configuration errors: does not break callers.
        """
        clean_email = to_email.strip().lower()
        notification = Notification(
            appointment_id=appointment_id,
            recipient=clean_email,
            notification_type=notification_type,
            status="pending",
            created_at=datetime.utcnow()
        )
        db.add(notification)
        db.flush()

        # If Brevo API key is not configured, simulate delivery in development/test mode
        if not settings.BREVO_API_KEY or settings.BREVO_API_KEY.startswith("test_") or settings.BREVO_API_KEY == "":
            notification.status = "sent"
            notification.error_message = "Development mode: Brevo API key not configured, simulated delivery."
            notification.sent_at = datetime.utcnow()
            db.commit()
            return True

        # Send real HTTP request to Brevo Transactional Email endpoint
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "api-key": settings.BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "sender": {
                "name": settings.BREVO_SENDER_NAME,
                "email": settings.BREVO_SENDER_EMAIL
            },
            "to": [{"email": clean_email, "name": to_name or clean_email}],
            "subject": subject,
            "htmlContent": html_content
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code in [200, 201, 202]:
                    notification.status = "sent"
                    notification.sent_at = datetime.utcnow()
                    notification.error_message = None
                    db.commit()
                    return True
                else:
                    notification.status = "failed"
                    notification.error_message = f"Brevo HTTP {response.status_code}: {response.text}"
                    db.commit()
                    return False
        except Exception as e:
            notification.status = "failed"
            notification.error_message = f"Brevo network error: {str(e)}"
            db.commit()
            return False

    @staticmethod
    def send_booking_confirmation(db: Session, appointment: Appointment) -> bool:
        if not appointment.patient or not appointment.patient.email:
            return False

        slot = appointment.slot
        slot_date = format_date_str(slot.start_time) if slot else "N/A"
        slot_time = format_slot_time(slot.start_time, slot.end_time) if slot else "N/A"

        context = {
            "patient_name": appointment.patient.full_name,
            "reference": appointment.reference,
            "doctor_name": appointment.doctor.name if appointment.doctor else "Hospital Specialist",
            "specialty_name": appointment.doctor.specialty.name if (appointment.doctor and appointment.doctor.specialty) else "General",
            "appointment_date": slot_date,
            "appointment_time": slot_time
        }
        html_body = render_template("booking_confirmation.html", context)
        return EmailService.send_email(
            db=db,
            to_email=appointment.patient.email,
            to_name=appointment.patient.full_name,
            subject=f"Confirmed: Your Doctor Appointment ({appointment.reference})",
            html_content=html_body,
            notification_type="booking_confirmation",
            appointment_id=appointment.id
        )

    @staticmethod
    def send_cancellation_confirmation(db: Session, appointment: Appointment) -> bool:
        if not appointment.patient or not appointment.patient.email:
            return False

        context = {
            "patient_name": appointment.patient.full_name,
            "reference": appointment.reference,
            "doctor_name": appointment.doctor.name if appointment.doctor else "Hospital Specialist",
            "specialty_name": appointment.doctor.specialty.name if (appointment.doctor and appointment.doctor.specialty) else "General"
        }
        html_body = render_template("cancellation.html", context)
        return EmailService.send_email(
            db=db,
            to_email=appointment.patient.email,
            to_name=appointment.patient.full_name,
            subject=f"Cancelled: Doctor Appointment ({appointment.reference})",
            html_content=html_body,
            notification_type="cancellation",
            appointment_id=appointment.id
        )

    @staticmethod
    def send_rescheduling_confirmation(
        db: Session,
        appointment: Appointment,
        old_date_str: Optional[str] = None,
        old_time_str: Optional[str] = None
    ) -> bool:
        if not appointment.patient or not appointment.patient.email:
            return False

        slot = appointment.slot
        new_date = format_date_str(slot.start_time) if slot else "N/A"
        new_time = format_slot_time(slot.start_time, slot.end_time) if slot else "N/A"

        context = {
            "patient_name": appointment.patient.full_name,
            "reference": appointment.reference,
            "doctor_name": appointment.doctor.name if appointment.doctor else "Hospital Specialist",
            "specialty_name": appointment.doctor.specialty.name if (appointment.doctor and appointment.doctor.specialty) else "General",
            "new_date": new_date,
            "new_time": new_time,
            "old_date": old_date_str,
            "old_time": old_time_str
        }
        html_body = render_template("rescheduling.html", context)
        return EmailService.send_email(
            db=db,
            to_email=appointment.patient.email,
            to_name=appointment.patient.full_name,
            subject=f"Rescheduled: Doctor Appointment ({appointment.reference})",
            html_content=html_body,
            notification_type="rescheduling",
            appointment_id=appointment.id
        )

    @staticmethod
    def send_booking_otp(
        db: Session,
        to_email: str,
        patient_name: str,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        otp: str
    ) -> bool:
        context = {
            "patient_name": patient_name,
            "doctor_name": doctor_name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "otp": otp,
            "expiry_minutes": settings.OTP_EXPIRY_MINUTES
        }
        html_body = render_template("booking_otp.html", context)
        return EmailService.send_email(
            db=db,
            to_email=to_email,
            to_name=patient_name,
            subject=f"Your MediDesk Booking Verification Code: {otp}",
            html_content=html_body,
            notification_type="otp"
        )

    @staticmethod
    def send_lookup_otp(
        db: Session,
        to_email: str,
        otp: str
    ) -> bool:
        context = {
            "otp": otp,
            "expiry_minutes": settings.OTP_EXPIRY_MINUTES
        }
        html_body = render_template("appointment_lookup_otp.html", context)
        return EmailService.send_email(
            db=db,
            to_email=to_email,
            to_name=to_email,
            subject=f"Your MediDesk Verification Code: {otp}",
            html_content=html_body,
            notification_type="otp"
        )

    @staticmethod
    def send_otp_email(
        db: Session,
        recipient_email: str = "",
        otp: str = "",
        purpose: str = "",
        appointment: Optional[Appointment] = None,
        context_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """
        Unified OTP dispatcher supporting all 4 purposes:
        - BOOKING
        - VIEW_APPOINTMENTS
        - CANCEL
        - RESCHEDULE
        """
        # Support legacy argument order: (db, appointment, recipient_email, otp, purpose)
        if kwargs.get("appointment"):
            appointment = kwargs["appointment"]
        if kwargs.get("recipient_email"):
            recipient_email = kwargs["recipient_email"]
        if kwargs.get("otp"):
            otp = kwargs["otp"]
        if kwargs.get("purpose"):
            purpose = kwargs["purpose"]

        clean_email = recipient_email.strip().lower()
        norm_purpose = purpose.upper()

        if norm_purpose == "BOOKING":
            ctx = context_data or {}
            return EmailService.send_booking_otp(
                db=db,
                to_email=clean_email,
                patient_name=ctx.get("patient_name", "Patient"),
                doctor_name=ctx.get("doctor_name", "Hospital Specialist"),
                appointment_date=ctx.get("appointment_date", "Selected Date"),
                appointment_time=ctx.get("appointment_time", "Selected Time"),
                otp=otp
            )
        elif norm_purpose in ["VIEW_APPOINTMENTS", "VIEW"]:
            return EmailService.send_lookup_otp(
                db=db,
                to_email=clean_email,
                otp=otp
            )
        elif norm_purpose == "CANCEL":
            ref = appointment.reference if appointment else (context_data.get("reference") if context_data else "N/A")
            context = {
                "reference": ref,
                "otp": otp,
                "expiry_minutes": settings.OTP_EXPIRY_MINUTES
            }
            html_body = render_template("cancellation_otp.html", context)
            return EmailService.send_email(
                db=db,
                to_email=clean_email,
                to_name=appointment.patient.full_name if (appointment and appointment.patient) else clean_email,
                subject=f"Cancellation Code for {ref}: {otp}",
                html_content=html_body,
                notification_type="otp",
                appointment_id=appointment.id if appointment else None
            )
        elif norm_purpose == "RESCHEDULE":
            ref = appointment.reference if appointment else (context_data.get("reference") if context_data else "N/A")
            context = {
                "reference": ref,
                "otp": otp,
                "expiry_minutes": settings.OTP_EXPIRY_MINUTES
            }
            html_body = render_template("rescheduling_otp.html", context)
            return EmailService.send_email(
                db=db,
                to_email=clean_email,
                to_name=appointment.patient.full_name if (appointment and appointment.patient) else clean_email,
                subject=f"Rescheduling Code for {ref}: {otp}",
                html_content=html_body,
                notification_type="otp",
                appointment_id=appointment.id if appointment else None
            )
        else:
            context = {
                "reference": appointment.reference if appointment else "N/A",
                "purpose": purpose,
                "otp": otp,
                "expiry_minutes": settings.OTP_EXPIRY_MINUTES
            }
            html_body = render_template("otp.html", context)
            return EmailService.send_email(
                db=db,
                to_email=clean_email,
                to_name=clean_email,
                subject=f"Your MediDesk Verification Code: {otp}",
                html_content=html_body,
                notification_type="otp",
                appointment_id=appointment.id if appointment else None
            )

    @staticmethod
    def send_reminder_24h(db: Session, appointment: Appointment) -> bool:
        if not appointment.patient or not appointment.patient.email or not appointment.slot:
            return False

        context = {
            "patient_name": appointment.patient.full_name,
            "reference": appointment.reference,
            "doctor_name": appointment.doctor.name if appointment.doctor else "Doctor",
            "specialty_name": appointment.doctor.specialty.name if (appointment.doctor and appointment.doctor.specialty) else "General",
            "appointment_date": format_date_str(appointment.slot.start_time),
            "appointment_time": format_slot_time(appointment.slot.start_time, appointment.slot.end_time)
        }
        html_body = render_template("reminder_24h.html", context)
        return EmailService.send_email(
            db=db,
            to_email=appointment.patient.email,
            to_name=appointment.patient.full_name,
            subject=f"Reminder: Your Appointment Tomorrow ({appointment.reference})",
            html_content=html_body,
            notification_type="reminder_24h",
            appointment_id=appointment.id
        )

    @staticmethod
    def send_reminder_2h(db: Session, appointment: Appointment) -> bool:
        if not appointment.patient or not appointment.patient.email or not appointment.slot:
            return False

        context = {
            "patient_name": appointment.patient.full_name,
            "reference": appointment.reference,
            "doctor_name": appointment.doctor.name if appointment.doctor else "Doctor",
            "specialty_name": appointment.doctor.specialty.name if (appointment.doctor and appointment.doctor.specialty) else "General",
            "appointment_time": format_slot_time(appointment.slot.start_time, appointment.slot.end_time)
        }
        html_body = render_template("reminder_2h.html", context)
        return EmailService.send_email(
            db=db,
            to_email=appointment.patient.email,
            to_name=appointment.patient.full_name,
            subject=f"Urgent Reminder: Appointment in 2 Hours ({appointment.reference})",
            html_content=html_body,
            notification_type="reminder_2h",
            appointment_id=appointment.id
        )

    @staticmethod
    def send_human_handoff_email(
        db: Session,
        session_id: int,
        reason: str,
        patient_contact: str
    ) -> bool:
        """Send notification to front desk staff when patient requests assistance."""
        html_body = f"""
        <h2>Human Handoff Request</h2>
        <p>A patient has requested human assistance via the MediDesk chat assistant.</p>
        <p><strong>Chat Session ID:</strong> {session_id}</p>
        <p><strong>Patient Contact:</strong> {patient_contact}</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p>Please reach out to the patient promptly.</p>
        """
        return EmailService.send_email(
            db=db,
            to_email=settings.FRONT_DESK_EMAIL,
            to_name="Hospital Front Desk Staff",
            subject="[Action Required] Patient Human Assistance Request",
            html_content=html_body,
            notification_type="handoff"
        )
