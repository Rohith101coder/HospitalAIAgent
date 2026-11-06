from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.core.security import decode_access_token
from app.models.admin import AdminUser
from app.schemas.appointment import (
    BookingInitiateRequest,
    BookingInitiateResponse,
    BookingConfirmRequest,
    AppointmentResponse,
    CancelAppointmentRequest,
    RescheduleAppointmentRequest,
    RequestOTPRequest,
    VerifyOTPRequest,
    OTPVerificationResponse,
    VerifiedAppointmentsResponse
)
from app.services.appointment_service import AppointmentService
from app.services.otp_service import OTPService
from app.services.patient_service import PatientService

router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


@router.post("/initiate", response_model=BookingInitiateResponse)
def initiate_booking(data: BookingInitiateRequest, db: Session = Depends(get_db)):
    """
    Step 1 of Guest Patient Booking:
    Validate doctor and slot, generate a booking request, and dispatch 6-digit OTP to patient's email.
    Does not reserve slot or create appointment until OTP is verified.
    """
    result = AppointmentService.initiate_booking(db=db, data=data)
    return BookingInitiateResponse(
        booking_request_reference=result["booking_request_reference"],
        doctor_name=result["doctor_name"],
        appointment_date=result["appointment_date"],
        appointment_time=result["appointment_time"],
        patient_email=result["patient_email"],
        message=result["message"]
    )


@router.post("/confirm", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def confirm_booking(data: BookingConfirmRequest, db: Session = Depends(get_db)):
    """
    Step 2 of Guest Patient Booking:
    Finalizes booking by verifying server-side verified status of the booking request,
    atomically reserving the slot, creating/reusing the patient contact record, and committing the appointment.
    """
    appointment = AppointmentService.confirm_booking(
        db=db,
        booking_request_reference=data.booking_request_reference,
        verification_token=data.verification_token
    )
    return AppointmentService.to_appointment_response(appointment)


@router.get("/verified", response_model=VerifiedAppointmentsResponse)
def get_verified_appointments(
    email: str = Query(..., description="Patient registered email address"),
    token: str = Query(..., description="Verified OTP token with purpose VIEW_APPOINTMENTS"),
    db: Session = Depends(get_db)
):
    """
    View appointments for an email address after OTP verification.
    No patient login or password required.
    """
    appointments = AppointmentService.get_verified_appointments(
        db=db,
        patient_email=email,
        verification_token=token
    )
    patient = PatientService.get_patient_by_email(db, email)
    return VerifiedAppointmentsResponse(
        patient_name=patient.full_name if patient else None,
        patient_email=email.strip().lower(),
        appointments=[AppointmentService.to_appointment_response(a) for a in appointments],
        total=len(appointments)
    )


@router.post("/request-otp")
def request_appointment_otp(data: RequestOTPRequest, db: Session = Depends(get_db)):
    """
    Request a one-time verification code (OTP) for:
    - BOOKING
    - VIEW_APPOINTMENTS
    - CANCEL
    - RESCHEDULE
    """
    OTPService.request_otp(
        db=db,
        patient_email=data.patient_email,
        purpose=data.purpose,
        booking_request_reference=data.booking_request_reference,
        reference=data.reference
    )
    return {
        "success": True,
        "message": f"Verification code has been sent to {data.patient_email}."
    }


@router.post("/verify-otp", response_model=OTPVerificationResponse)
def verify_appointment_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Verify submitted OTP code and receive an authorization token for the action."""
    token = OTPService.verify_otp(
        db=db,
        patient_email=data.patient_email,
        submitted_otp=data.otp,
        purpose=data.purpose,
        booking_request_reference=data.booking_request_reference,
        reference=data.reference
    )
    return OTPVerificationResponse(
        success=True,
        verification_token=token,
        message="Identity verified successfully. You may now proceed."
    )


@router.post("/cancel", response_model=AppointmentResponse)
def cancel_appointment(data: CancelAppointmentRequest, db: Session = Depends(get_db)):
    """Cancel an appointment. Requires verified OTP authorization token."""
    if not data.verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is required to cancel an appointment."
        )
    appointment = AppointmentService.cancel_appointment(
        db=db,
        reference=data.reference,
        verification_token=data.verification_token,
        reason=data.reason,
        changed_by="patient"
    )
    return AppointmentService.to_appointment_response(appointment)


@router.post("/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(data: RescheduleAppointmentRequest, db: Session = Depends(get_db)):
    """Reschedule an appointment to a new slot. Requires verified OTP authorization token."""
    if not data.verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is required to reschedule an appointment."
        )
    appointment = AppointmentService.reschedule_appointment(
        db=db,
        reference=data.reference,
        new_slot_id=data.new_slot_id,
        verification_token=data.verification_token,
        changed_by="patient"
    )
    return AppointmentService.to_appointment_response(appointment)


@router.get("", response_model=List[AppointmentResponse])
def list_appointments(
    status: Optional[str] = Query(None, description="Filter by status (booked, confirmed, cancelled, etc.)"),
    doctor_id: Optional[int] = Query(None, description="Filter by doctor ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """List appointments with filtering (Admin only)."""
    appointments = AppointmentService.get_appointments_list(
        db=db,
        status_filter=status,
        doctor_id=doctor_id,
        limit=limit,
        offset=offset
    )
    return [AppointmentService.to_appointment_response(a) for a in appointments]


@router.get("/{reference}", response_model=AppointmentResponse)
def get_appointment(
    reference: str,
    token: Optional[str] = Query(None, description="Verified OTP action token"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Retrieve appointment details using unique booking reference.
    Requires verified patient OTP token or Admin authorization.
    """
    token_str = token
    is_admin = False

    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization.split(" ", 1)[1]
        payload = decode_access_token(bearer_token)
        if payload and payload.get("type") == "admin":
            is_admin = True
        elif not token_str:
            token_str = bearer_token

    appointment = AppointmentService.get_appointment_by_reference(
        db=db,
        reference=reference,
        verification_token=token_str,
        is_admin=is_admin
    )
    return AppointmentService.to_appointment_response(appointment)
