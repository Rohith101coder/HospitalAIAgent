from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class BookingInitiateRequest(BaseModel):
    doctor_id: int
    slot_id: int
    patient_name: str = Field(..., min_length=2, max_length=150)
    patient_phone: str = Field(..., min_length=7, max_length=20)
    patient_email: EmailStr
    reason: Optional[str] = None


class BookingInitiateResponse(BaseModel):
    booking_request_reference: str
    doctor_name: str
    appointment_date: str
    appointment_time: str
    patient_email: str
    message: str


class RequestOTPRequest(BaseModel):
    patient_email: EmailStr
    purpose: str = Field(..., description="BOOKING, VIEW_APPOINTMENTS, CANCEL, or RESCHEDULE")
    booking_request_reference: Optional[str] = None
    reference: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    patient_email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    purpose: str = Field(..., description="BOOKING, VIEW_APPOINTMENTS, CANCEL, or RESCHEDULE")
    booking_request_reference: Optional[str] = None
    reference: Optional[str] = None


class OTPVerificationResponse(BaseModel):
    success: bool
    verification_token: str
    message: str


class BookingConfirmRequest(BaseModel):
    booking_request_reference: str
    verification_token: Optional[str] = None


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    patient_id: int
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_id: int
    doctor_name: Optional[str] = None
    specialty_name: Optional[str] = None
    slot_id: Optional[int] = None
    slot_start_time: Optional[datetime] = None
    slot_end_time: Optional[datetime] = None
    display_date: Optional[str] = None
    display_time: Optional[str] = None
    status: str
    reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CancelAppointmentRequest(BaseModel):
    reference: str
    verification_token: str
    reason: Optional[str] = None


class RescheduleAppointmentRequest(BaseModel):
    reference: str
    new_slot_id: int
    verification_token: str


class VerifiedAppointmentsResponse(BaseModel):
    patient_name: Optional[str] = None
    patient_email: str
    appointments: List[AppointmentResponse]
    total: int
