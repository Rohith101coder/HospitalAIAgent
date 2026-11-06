from datetime import datetime
from sqlalchemy import Column, BigInteger, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class DoctorSlot(Base):
    __tablename__ = "doctor_slots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="available", nullable=False, index=True)  # available, booked, blocked
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("doctor_id", "start_time", name="uq_doctor_slot_start"),
    )

    doctor = relationship("Doctor", back_populates="slots")
    appointment = relationship("Appointment", back_populates="slot", uselist=False)

