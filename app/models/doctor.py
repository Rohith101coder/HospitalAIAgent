from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    specialty_id = Column(BigInteger, ForeignKey("specialties.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    qualification = Column(String(100), nullable=False)
    experience_years = Column(Integer, nullable=False, default=0)
    languages = Column(JSON, nullable=False, default=list)  # list of strings: ["English", "Telugu", "Hindi"]
    consultation_fee = Column(Numeric(10, 2), nullable=False, default=0.00)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    specialty = relationship("Specialty", back_populates="doctors")
    schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")
    schedule_exceptions = relationship("DoctorScheduleException", back_populates="doctor", cascade="all, delete-orphan")
    slots = relationship("DoctorSlot", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor")

