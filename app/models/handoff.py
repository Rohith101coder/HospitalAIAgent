from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime
from app.core.database import Base


class HumanHandoff(Base):
    __tablename__ = "human_handoffs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, nullable=True)  # Legacy/Optional identifier
    reason = Column(Text, nullable=False)
    patient_contact = Column(String(150), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, resolved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
