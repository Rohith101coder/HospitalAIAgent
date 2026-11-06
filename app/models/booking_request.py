from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class BookingRequest(Base):
    __tablename__ = "booking_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reference = Column(String(64), unique=True, nullable=False, index=True)
    patient_name = Column(String(150), nullable=False)
    normalized_email = Column(String(150), nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False)
    slot_id = Column(BigInteger, ForeignKey("doctor_slots.id"), nullable=False)
    appointment_reason = Column(Text, nullable=True)
    status = Column(String(30), default="pending_otp", nullable=False, index=True)  # pending_otp, verified, completed, expired
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor")
    slot = relationship("DoctorSlot")
    otp_verifications = relationship("OTPVerification", back_populates="booking_request", cascade="all, delete-orphan")

