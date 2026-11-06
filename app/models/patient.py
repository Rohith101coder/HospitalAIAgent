from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    full_name = Column(String(150), nullable=False)
    normalized_email = Column(String(150), unique=True, nullable=False, index=True)
    email = Column(String(150), nullable=True)  # Backward-compatible column in DB
    phone = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
