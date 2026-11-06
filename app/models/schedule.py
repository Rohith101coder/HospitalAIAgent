from datetime import datetime
from sqlalchemy import Column, BigInteger, Integer, Time, Date, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False, index=True)
    weekday = Column(Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_duration_minutes = Column(Integer, default=30, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor", back_populates="schedules")


class DoctorScheduleException(Base):
    __tablename__ = "doctor_schedule_exceptions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    doctor_id = Column(BigInteger, ForeignKey("doctors.id"), nullable=False, index=True)
    exception_date = Column(Date, nullable=False, index=True)
    exception_type = Column(String(50), nullable=False)  # 'holiday', 'leave', 'modified_hours'
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("Doctor", back_populates="schedule_exceptions")

