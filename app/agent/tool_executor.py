from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.services.doctor_service import DoctorService
from app.services.slot_service import SlotService
from app.services.appointment_service import AppointmentService
from app.services.otp_service import OTPService
from app.services.email_service import EmailService
from app.schemas.appointment import BookingInitiateRequest
from app.models.handoff import HumanHandoff
from app.utils.datetime_utils import format_slot_time, format_date_str


class ToolExecutor:
    """Executes tool calls within a request-scoped database transaction."""

    def __init__(self, db: Session):
        self.db = db

    def find_doctors(self, specialty: str) -> Dict[str, Any]:
        """Find active doctors by specialty name."""
        try:
            doctors = DoctorService.search_doctors_by_specialty(self.db, specialty)
            if not doctors:
                return {
                    "success": True,
                    "doctors": [],
                    "message": f"No active doctors found for specialty '{specialty}'."
                }
            results = []
            for d in doctors:
                results.append({
                    "doctor_id": d.id,
                    "name": d.name,
                    "specialty": d.specialty.name if d.specialty else specialty,
                    "qualification": d.qualification,
                    "experience_years": d.experience_years,
                    "languages": d.languages,
                    "consultation_fee": float(d.consultation_fee),
                    "description": d.description
                })
            return {"success": True, "doctors": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_doctor_details(self, doctor_id: int) -> Dict[str, Any]:
        """Retrieve complete information for a specific doctor."""
        try:
            doc = DoctorService.get_doctor_by_id(self.db, doctor_id)
            return {
                "success": True,
                "doctor": {
                    "doctor_id": doc.id,
                    "name": doc.name,
                    "specialty": doc.specialty.name if doc.specialty else "General",
                    "qualification": doc.qualification,
                    "experience_years": doc.experience_years,
                    "languages": doc.languages,
                    "consultation_fee": float(doc.consultation_fee),
                    "description": doc.description
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_available_slots(self, doctor_id: int, date_str: str) -> Dict[str, Any]:
        """Find available appointment slots for doctor on date YYYY-MM-DD."""
        try:
            target_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
            slots = SlotService.get_slots_by_doctor_and_date(
                db=self.db,
                doctor_id=doctor_id,
                target_date=target_date,
                available_only=True
            )
            return {
                "success": True,
                "doctor_id": doctor_id,
                "date": date_str,
                "available_slots": slots,
                "count": len(slots)
            }
        except ValueError:
            return {"success": False, "error": f"Invalid date format '{date_str}'. Please use YYYY-MM-DD."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def initiate_booking(
        self,
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        doctor_id: int,
        slot_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate doctor and slot, create temporary booking request, and dispatch 6-digit OTP code to email."""
        try:
            req = BookingInitiateRequest(
                patient_name=patient_name,
                patient_email=patient_email,
                patient_phone=patient_phone,
                doctor_id=doctor_id,
                slot_id=slot_id,
                reason=reason
            )
            result = AppointmentService.initiate_booking(db=self.db, data=req)
            return {
                "success": True,
                "booking_request_reference": result["booking_request_reference"],
                "doctor_name": result["doctor_name"],
                "appointment_date": result["appointment_date"],
                "appointment_time": result["appointment_time"],
                "patient_email": result["patient_email"],
                "message": result["message"]
            }
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error_code": "INITIATION_FAILED", "message": detail}

    def request_appointment_otp(
        self,
        patient_email: str,
        purpose: str,
        booking_request_reference: Optional[str] = None,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Request verification OTP for BOOKING, VIEW_APPOINTMENTS, CANCEL, or RESCHEDULE."""
        try:
            OTPService.request_otp(
                db=self.db,
                patient_email=patient_email,
                purpose=purpose,
                booking_request_reference=booking_request_reference,
                reference=reference
            )
            return {
                "success": True,
                "purpose": purpose.upper(),
                "patient_email": patient_email.strip().lower(),
                "message": f"A 6-digit verification code has been sent to {patient_email}. Please provide the code to proceed."
            }
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error": detail}

    def verify_appointment_otp(
        self,
        patient_email: str,
        otp: str,
        purpose: str,
        booking_request_reference: Optional[str] = None,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify submitted OTP code:
        - If BOOKING: verifies OTP and marks booking request as verified. Auto-completes booking if booking_request_reference is provided.
        - If VIEW_APPOINTMENTS: retrieves and returns list of appointments.
        - If CANCEL or RESCHEDULE: returns verification_token for subsequent action execution.
        """
        try:
            norm_purpose = purpose.upper()

            # Verify OTP and get token
            token = OTPService.verify_otp(
                db=self.db,
                patient_email=patient_email,
                submitted_otp=otp,
                purpose=norm_purpose,
                booking_request_reference=booking_request_reference,
                reference=reference
            )

            # Workflow branching based on purpose
            if norm_purpose == "BOOKING":
                ref = booking_request_reference or reference
                if ref:
                    return self.confirm_booking(booking_request_reference=ref, verification_token=token)
                return {
                    "success": True,
                    "verification_token": token,
                    "message": "OTP verified successfully. You may now call confirm_booking."
                }

            elif norm_purpose in ["VIEW_APPOINTMENTS", "VIEW"]:
                appointments = AppointmentService.get_verified_appointments(
                    db=self.db,
                    patient_email=patient_email,
                    verification_token=token
                )
                appts_data = []
                for a in appointments:
                    s = a.slot
                    appts_data.append({
                        "reference": a.reference,
                        "doctor": a.doctor.name if a.doctor else "Doctor",
                        "specialty": a.doctor.specialty.name if (a.doctor and a.doctor.specialty) else "General",
                        "date": format_date_str(s.start_time) if s else "N/A",
                        "time": format_slot_time(s.start_time, s.end_time) if s else "N/A",
                        "status": a.status,
                        "reason": a.reason
                    })
                return {
                    "success": True,
                    "verification_token": token,
                    "appointments": appts_data,
                    "total": len(appts_data),
                    "message": f"Found {len(appts_data)} appointment(s) registered under {patient_email}."
                }

            else:
                # CANCEL or RESCHEDULE
                return {
                    "success": True,
                    "verification_token": token,
                    "reference": reference,
                    "purpose": norm_purpose,
                    "message": "Verification code verified successfully. You are authorized to proceed."
                }

        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error": detail}

    def confirm_booking(
        self,
        booking_request_reference: str,
        verification_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Atomically finalize booking after OTP verification."""
        try:
            appointment = AppointmentService.confirm_booking(
                db=self.db,
                booking_request_reference=booking_request_reference,
                verification_token=verification_token
            )
            slot = appointment.slot
            display_date = format_date_str(slot.start_time) if slot else "N/A"
            display_time = format_slot_time(slot.start_time, slot.end_time) if slot else "N/A"

            return {
                "success": True,
                "reference": appointment.reference,
                "doctor": appointment.doctor.name if appointment.doctor else "Doctor",
                "specialty": appointment.doctor.specialty.name if (appointment.doctor and appointment.doctor.specialty) else "General",
                "date": display_date,
                "time": display_time,
                "patient_name": appointment.patient.full_name if appointment.patient else "Patient",
                "patient_email": appointment.patient.normalized_email if appointment.patient else "",
                "message": f"Appointment booked successfully! Booking Reference: {appointment.reference}. A confirmation email has been sent."
            }
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error": detail}

    def get_my_appointments(
        self,
        patient_email: Optional[str] = None,
        verification_token: Optional[str] = None,
        reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve booking details by reference or patient email."""
        try:
            if reference and verification_token:
                appt = AppointmentService.get_appointment_by_reference(
                    self.db,
                    reference=reference,
                    verification_token=verification_token
                )
                slot = appt.slot
                return {
                    "success": True,
                    "appointment": {
                        "reference": appt.reference,
                        "doctor": appt.doctor.name if appt.doctor else "Doctor",
                        "specialty": appt.doctor.specialty.name if (appt.doctor and appt.doctor.specialty) else "General",
                        "date": format_date_str(slot.start_time) if slot else "Cancelled/Released",
                        "time": format_slot_time(slot.start_time, slot.end_time) if slot else "Cancelled/Released",
                        "status": appt.status,
                        "patient_name": appt.patient.full_name if appt.patient else "Patient"
                    }
                }
            elif patient_email and verification_token:
                appointments = AppointmentService.get_verified_appointments(
                    db=self.db,
                    patient_email=patient_email,
                    verification_token=verification_token
                )
                appts_data = []
                for a in appointments:
                    s = a.slot
                    appts_data.append({
                        "reference": a.reference,
                        "doctor": a.doctor.name if a.doctor else "Doctor",
                        "specialty": a.doctor.specialty.name if (a.doctor and a.doctor.specialty) else "General",
                        "date": format_date_str(s.start_time) if s else "N/A",
                        "time": format_slot_time(s.start_time, s.end_time) if s else "N/A",
                        "status": a.status,
                        "reason": a.reason
                    })
                return {
                    "success": True,
                    "appointments": appts_data,
                    "total": len(appts_data)
                }
            else:
                return {
                    "success": False,
                    "error": "Please provide your verified email token (or reference with verification token) to view appointments."
                }
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error": detail}

    def cancel_appointment(self, reference: str, verification_token: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Cancel appointment with verified authorization token."""
        try:
            appt = AppointmentService.cancel_appointment(
                db=self.db,
                reference=reference,
                verification_token=verification_token,
                reason=reason,
                changed_by="patient"
            )
            return {
                "success": True,
                "reference": appt.reference,
                "status": "cancelled",
                "message": "Your appointment has been successfully cancelled. The doctor's slot is now released."
            }
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error": detail}

    def reschedule_appointment(self, reference: str, new_slot_id: int, verification_token: str) -> Dict[str, Any]:
        """Reschedule appointment with verified authorization token."""
        try:
            appt = AppointmentService.reschedule_appointment(
                db=self.db,
                reference=reference,
                new_slot_id=new_slot_id,
                verification_token=verification_token,
                changed_by="patient"
            )
            slot = appt.slot
            display_date = format_date_str(slot.start_time) if slot else "N/A"
            display_time = format_slot_time(slot.start_time, slot.end_time) if slot else "N/A"

            return {
                "success": True,
                "reference": appt.reference,
                "date": display_date,
                "time": display_time,
                "message": "Your appointment has been successfully rescheduled to the new time!"
            }
        except Exception as e:
            detail = getattr(e, "detail", str(e))
            return {"success": False, "error": detail}

    def request_human_handoff(self, reason: str, patient_contact: str) -> Dict[str, Any]:
        """Record patient request for hospital staff assistance."""
        try:
            handoff = HumanHandoff(
                session_id=None,
                reason=reason,
                patient_contact=patient_contact,
                status="pending"
            )
            self.db.add(handoff)
            self.db.commit()

            EmailService.send_human_handoff_email(
                db=self.db,
                session_id=0,
                reason=reason,
                patient_contact=patient_contact
            )

            return {
                "success": True,
                "message": "Hospital staff have been alerted and will reach out to you shortly."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
