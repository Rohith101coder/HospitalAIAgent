from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Boolean, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_email = Column(String(150), nullable=False, index=True)
    otp_hash = Column(String(255), nullable=False)
    purpose = Column(String(50), nullable=False, index=True)  # BOOKING, VIEW_APPOINTMENTS, CANCEL, RESCHEDULE
    booking_request_id = Column(BigInteger, ForeignKey("booking_requests.id"), nullable=True, index=True)
    booking_request_reference = Column(String(64), nullable=True, index=True)
    appointment_id = Column(BigInteger, ForeignKey("appointments.id"), nullable=True, index=True)
    booking_context_hash = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="otp_verifications")
    booking_request = relationship("BookingRequest", back_populates="otp_verifications")
