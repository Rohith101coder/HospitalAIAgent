from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class AppointmentHistory(Base):
    __tablename__ = "appointment_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id = Column(BigInteger, ForeignKey("appointments.id"), nullable=False, index=True)
    old_slot_id = Column(BigInteger, nullable=True)
    new_slot_id = Column(BigInteger, nullable=True)
    action = Column(String(50), nullable=False)  # booked, rescheduled, cancelled, confirmed, completed, no_show
    changed_by = Column(String(50), nullable=False, default="patient")  # patient, admin, system
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="history")

