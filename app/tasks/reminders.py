from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.appointment import Appointment
from app.models.slot import DoctorSlot
from app.models.notification import Notification
from app.services.email_service import EmailService

# Global scheduler instance
scheduler = BackgroundScheduler(timezone=settings.HOSPITAL_TIMEZONE)


def run_24h_reminders() -> Tuple[int, int]:
    """
    Find appointments starting in ~24 hours (between 23 and 25 hours ahead)
    that have not yet received a 24-hour reminder notification.
    Returns (eligible_count, sent_count).
    """
    db: Session = SessionLocal()
    eligible_count = 0
    sent_count = 0
    now = datetime.utcnow()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)

    try:
        appointments = (
            db.query(Appointment)
            .join(DoctorSlot, Appointment.slot_id == DoctorSlot.id)
            .filter(
                Appointment.status.in_(["booked", "confirmed"]),
                DoctorSlot.start_time >= window_start,
                DoctorSlot.start_time <= window_end
            )
            .all()
        )

        eligible_count = len(appointments)

        for appt in appointments:
            # Check database-level deduplication
            existing = (
                db.query(Notification)
                .filter(
                    Notification.appointment_id == appt.id,
                    Notification.notification_type == "reminder_24h",
                    Notification.status.in_(["sent", "pending"])
                )
                .first()
            )

            if existing:
                continue

            success = EmailService.send_reminder_24h(db, appt)
            if success:
                sent_count += 1

    except Exception as e:
        print(f"Error during 24h reminder job execution: {e}")
    finally:
        db.close()

    return eligible_count, sent_count


def run_2h_reminders() -> Tuple[int, int]:
    """
    Find appointments starting in ~2 hours (between 1.5 and 2.5 hours ahead)
    that have not yet received a 2-hour reminder notification.
    Returns (eligible_count, sent_count).
    """
    db: Session = SessionLocal()
    eligible_count = 0
    sent_count = 0
    now = datetime.utcnow()
    window_start = now + timedelta(hours=1, minutes=30)
    window_end = now + timedelta(hours=2, minutes=30)

    try:
        appointments = (
            db.query(Appointment)
            .join(DoctorSlot, Appointment.slot_id == DoctorSlot.id)
            .filter(
                Appointment.status.in_(["booked", "confirmed"]),
                DoctorSlot.start_time >= window_start,
                DoctorSlot.start_time <= window_end
            )
            .all()
        )

        eligible_count = len(appointments)

        for appt in appointments:
            # Check database-level deduplication
            existing = (
                db.query(Notification)
                .filter(
                    Notification.appointment_id == appt.id,
                    Notification.notification_type == "reminder_2h",
                    Notification.status.in_(["sent", "pending"])
                )
                .first()
            )

            if existing:
                continue

            success = EmailService.send_reminder_2h(db, appt)
            if success:
                sent_count += 1

    except Exception as e:
        print(f"Error during 2h reminder job execution: {e}")
    finally:
        db.close()

    return eligible_count, sent_count


def start_scheduler():
    """Start APScheduler background jobs."""
    if not settings.ENABLE_SCHEDULER:
        print("Background reminder scheduler is disabled by config.")
        return

    if not scheduler.running:
        # Schedule 24h reminder to run every 15 minutes
        scheduler.add_job(
            run_24h_reminders,
            "interval",
            minutes=15,
            id="job_24h_reminders",
            replace_existing=True
        )
        # Schedule 2h reminder to run every 10 minutes
        scheduler.add_job(
            run_2h_reminders,
            "interval",
            minutes=10,
            id="job_2h_reminders",
            replace_existing=True
        )
        scheduler.start()
        print("APScheduler started with 24h and 2h reminder interval jobs.")


def stop_scheduler():
    """Stop APScheduler cleanly."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("APScheduler shut down.")

