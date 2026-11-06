import json
from typing import List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from app.agent.tool_executor import ToolExecutor


# Pydantic Schemas for Tools

class FindDoctorsInput(BaseModel):
    specialty: str = Field(..., description="Medical specialty to search, e.g. Cardiology, Neurology, Pediatrics, Orthopedics, Dermatology, General Medicine, Gynecology")


class GetDoctorDetailsInput(BaseModel):
    doctor_id: int = Field(..., description="The ID of the doctor")


class GetAvailableSlotsInput(BaseModel):
    doctor_id: int = Field(..., description="The ID of the doctor")
    date: str = Field(..., description="Date for consultation in YYYY-MM-DD format (must be today or future date)")


class InitiateBookingInput(BaseModel):
    patient_name: str = Field(..., description="Full legal name of the patient")
    patient_email: str = Field(..., description="Active email address of the patient")
    patient_phone: str = Field(..., description="Active mobile phone number of the patient")
    doctor_id: int = Field(..., description="The ID of the doctor")
    slot_id: int = Field(..., description="The ID of the chosen available slot")
    reason: Optional[str] = Field(None, description="Reason for medical consultation or symptoms")


class RequestAppointmentOTPInput(BaseModel):
    patient_email: str = Field(..., description="Patient's email address where OTP should be sent")
    purpose: str = Field(..., description="Must be one of: 'BOOKING', 'VIEW_APPOINTMENTS', 'CANCEL', 'RESCHEDULE'")
    booking_request_reference: Optional[str] = Field(None, description="Temporary booking request reference (BREQ-XXXXXX) for BOOKING")
    reference: Optional[str] = Field(None, description="Appointment reference code (MED-2026-XXXXX), required for CANCEL or RESCHEDULE")


class VerifyAppointmentOTPInput(BaseModel):
    patient_email: str = Field(..., description="Patient email address")
    otp: str = Field(..., description="The 6-digit verification code received by email")
    purpose: str = Field(..., description="Must be one of: 'BOOKING', 'VIEW_APPOINTMENTS', 'CANCEL', 'RESCHEDULE'")
    booking_request_reference: Optional[str] = Field(None, description="Temporary booking request reference (BREQ-XXXXXX) if purpose is BOOKING")
    reference: Optional[str] = Field(None, description="Appointment reference code (MED-2026-XXXXX) if purpose is CANCEL or RESCHEDULE")


class ConfirmBookingInput(BaseModel):
    booking_request_reference: str = Field(..., description="The temporary booking request reference code, e.g. BREQ-XXXXXX")
    verification_token: Optional[str] = Field(None, description="Optional authorization token returned by verify_appointment_otp")


class GetMyAppointmentsInput(BaseModel):
    patient_email: Optional[str] = Field(None, description="Patient registered email address")
    verification_token: Optional[str] = Field(None, description="Verified authorization token for email lookup")
    reference: Optional[str] = Field(None, description="Specific appointment reference code, e.g. MED-2026-XXXXX")


class CancelAppointmentInput(BaseModel):
    reference: str = Field(..., description="The booking reference code, e.g. MED-2026-XXXXX")
    verification_token: str = Field(..., description="The security token obtained from verify_appointment_otp")
    reason: Optional[str] = Field(None, description="Optional cancellation reason")


class RescheduleAppointmentInput(BaseModel):
    reference: str = Field(..., description="The booking reference code, e.g. MED-2026-XXXXX")
    new_slot_id: int = Field(..., description="The slot ID of the new available appointment time")
    verification_token: str = Field(..., description="The security token obtained from verify_appointment_otp")


class RequestHumanHandoffInput(BaseModel):
    reason: str = Field(..., description="Reason patient needs hospital staff assistance")
    patient_contact: str = Field(..., description="Patient phone number or contact info")


def get_tools(executor: ToolExecutor) -> list:
    """Generate request-scoped LangChain tools bound to executor."""

    @tool(args_schema=FindDoctorsInput)
    def find_doctors(specialty: str) -> str:
        """Search active hospital doctors by medical specialty (e.g. Cardiology, Neurology, Dermatology, Pediatrics, Orthopedics, General Medicine, Gynecology). Returns doctor list with qualifications, fees, and languages."""
        result = executor.find_doctors(specialty)
        return json.dumps(result)

    @tool(args_schema=GetDoctorDetailsInput)
    def get_doctor_details(doctor_id: int) -> str:
        """Get full profile details for a doctor given their doctor ID."""
        result = executor.get_doctor_details(doctor_id)
        return json.dumps(result)

    @tool(args_schema=GetAvailableSlotsInput)
    def get_available_slots(doctor_id: int, date: str) -> str:
        """Find available future consultation slots for a doctor on a specific calendar date (YYYY-MM-DD)."""
        result = executor.get_available_slots(doctor_id, date)
        return json.dumps(result)

    @tool(args_schema=InitiateBookingInput)
    def initiate_booking(
        patient_name: str,
        patient_email: str,
        patient_phone: str,
        doctor_id: int,
        slot_id: int,
        reason: Optional[str] = None
    ) -> str:
        """Initiate appointment booking by validating doctor/slot, creating a temporary booking request, and sending a 6-digit verification code (OTP) to the patient's email. Call this when patient confirms booking details."""
        result = executor.initiate_booking(
            patient_name=patient_name,
            patient_email=patient_email,
            patient_phone=patient_phone,
            doctor_id=doctor_id,
            slot_id=slot_id,
            reason=reason
        )
        return json.dumps(result)

    @tool(args_schema=RequestAppointmentOTPInput)
    def request_appointment_otp(
        patient_email: str,
        purpose: str,
        booking_request_reference: Optional[str] = None,
        reference: Optional[str] = None
    ) -> str:
        """Send a 6-digit email OTP verification code to the patient to authorize BOOKING, VIEW_APPOINTMENTS, CANCEL, or RESCHEDULE."""
        result = executor.request_appointment_otp(
            patient_email=patient_email,
            purpose=purpose,
            booking_request_reference=booking_request_reference,
            reference=reference
        )
        return json.dumps(result)

    @tool(args_schema=VerifyAppointmentOTPInput)
    def verify_appointment_otp(
        patient_email: str,
        otp: str,
        purpose: str,
        booking_request_reference: Optional[str] = None,
        reference: Optional[str] = None
    ) -> str:
        """Verify the 6-digit email OTP code. For BOOKING: verifies OTP and confirms booking! For VIEW_APPOINTMENTS: returns patient's appointments. For CANCEL/RESCHEDULE: returns verification_token."""
        result = executor.verify_appointment_otp(
            patient_email=patient_email,
            otp=otp,
            purpose=purpose,
            booking_request_reference=booking_request_reference,
            reference=reference
        )
        return json.dumps(result)

    @tool(args_schema=ConfirmBookingInput)
    def confirm_booking(
        booking_request_reference: str,
        verification_token: Optional[str] = None
    ) -> str:
        """Atomically finalize and reserve an appointment using the verified booking request reference."""
        result = executor.confirm_booking(
            booking_request_reference=booking_request_reference,
            verification_token=verification_token
        )
        return json.dumps(result)

    @tool(args_schema=GetMyAppointmentsInput)
    def get_my_appointments(
        patient_email: Optional[str] = None,
        verification_token: Optional[str] = None,
        reference: Optional[str] = None
    ) -> str:
        """Retrieve booking details using either patient email with verification_token or specific reference with token."""
        result = executor.get_my_appointments(
            patient_email=patient_email,
            verification_token=verification_token,
            reference=reference
        )
        return json.dumps(result)

    @tool(args_schema=CancelAppointmentInput)
    def cancel_appointment(reference: str, verification_token: str, reason: Optional[str] = None) -> str:
        """Cancel an appointment and release its slot. Requires verification_token from verify_appointment_otp."""
        result = executor.cancel_appointment(reference, verification_token, reason)
        return json.dumps(result)

    @tool(args_schema=RescheduleAppointmentInput)
    def reschedule_appointment(reference: str, new_slot_id: int, verification_token: str) -> str:
        """Reschedule an appointment to a new slot. Requires verification_token from verify_appointment_otp."""
        result = executor.reschedule_appointment(reference, new_slot_id, verification_token)
        return json.dumps(result)

    @tool(args_schema=RequestHumanHandoffInput)
    def request_human_handoff(reason: str, patient_contact: str) -> str:
        """Request assistance from hospital human staff when a patient needs human help."""
        result = executor.request_human_handoff(reason, patient_contact)
        return json.dumps(result)

    return [
        find_doctors,
        get_doctor_details,
        get_available_slots,
        initiate_booking,
        request_appointment_otp,
        verify_appointment_otp,
        confirm_booking,
        get_my_appointments,
        cancel_appointment,
        reschedule_appointment,
        request_human_handoff,
    ]
