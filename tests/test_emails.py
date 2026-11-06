from app.models.appointment import Appointment
from app.models.notification import Notification
from app.services.email_service import EmailService


def test_booking_confirmation_email_logging(db_session):
    appt = db_session.query(Appointment).first()
    assert appt is not None

    success = EmailService.send_booking_confirmation(db_session, appt)
    assert success is True

    # Check notification logged
    log = (
        db_session.query(Notification)
        .filter(
            Notification.appointment_id == appt.id,
            Notification.notification_type == "booking_confirmation"
        )
        .order_by(Notification.created_at.desc())
        .first()
    )
    assert log is not None
    assert log.recipient == appt.patient.email
    assert log.status in ["sent", "pending"]


def test_cancellation_email_logging(db_session):
    appt = db_session.query(Appointment).first()
    assert appt is not None

    success = EmailService.send_cancellation_confirmation(db_session, appt)
    assert success is True

    log = (
        db_session.query(Notification)
        .filter(
            Notification.appointment_id == appt.id,
            Notification.notification_type == "cancellation"
        )
        .order_by(Notification.created_at.desc())
        .first()
    )
    assert log is not None
    assert log.recipient == appt.patient.email


def test_otp_email_logging(db_session):
    appt = db_session.query(Appointment).first()
    assert appt is not None

    success = EmailService.send_otp_email(
        db=db_session,
        appointment=appt,
        recipient_email=appt.patient.email,
        otp="123456",
        purpose="cancel"
    )
    assert success is True

    log = (
        db_session.query(Notification)
        .filter(
            Notification.appointment_id == appt.id,
            Notification.notification_type == "otp"
        )
        .order_by(Notification.created_at.desc())
        .first()
    )
    assert log is not None


def test_reminder_emails_logging(db_session):
    appt = db_session.query(Appointment).first()
    assert appt is not None

    s24 = EmailService.send_reminder_24h(db_session, appt)
    assert s24 is True
    s2 = EmailService.send_reminder_2h(db_session, appt)
    assert s2 is True

