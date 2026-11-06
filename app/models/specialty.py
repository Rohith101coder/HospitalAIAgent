from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


class Specialty(Base):
    __tablename__ = "specialties"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctors = relationship("Doctor", back_populates="specialty")

