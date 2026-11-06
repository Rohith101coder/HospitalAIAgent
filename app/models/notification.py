from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id = Column(BigInteger, ForeignKey("appointments.id"), nullable=True, index=True)
    recipient = Column(String(150), nullable=False)
    notification_type = Column(String(50), nullable=False)  # booking_confirmation, cancellation, rescheduling, reminder_24h, reminder_2h, otp, handoff
    status = Column(String(20), default="pending", nullable=False)  # pending, sent, failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="notifications")

