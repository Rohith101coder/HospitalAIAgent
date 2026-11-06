from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reference = Column(String(50), unique=True, nullable=False, index=True)
    patient_id = Column(BigInteger, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False, index=True)
    slot_id = Column(BigInteger, ForeignKey("doctor_slots.id"), nullable=True, unique=True, index=True)
    status = Column(String(20), default="booked", nullable=False, index=True)  # booked, confirmed, cancelled, completed, no_show
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    slot = relationship("DoctorSlot", back_populates="appointment")
    history = relationship("AppointmentHistory", back_populates="appointment", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="appointment", cascade="all, delete-orphan")
    otp_verifications = relationship("OTPVerification", back_populates="appointment", cascade="all, delete-orphan")

    @property
    def appointment_reason(self) -> str:
        return self.reason

    @appointment_reason.setter
    def appointment_reason(self, value: str) -> None:
        self.reason = value
