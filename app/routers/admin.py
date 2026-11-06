from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.specialty import Specialty
from app.models.patient import Patient
from app.models.notification import Notification
from app.models.handoff import HumanHandoff
from app.services.appointment_service import AppointmentService
from app.tasks.reminders import run_24h_reminders, run_2h_reminders

router = APIRouter(prefix="/api/admin", tags=["Admin Operations"])


@router.get("/stats")
def get_hospital_stats(
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
) -> Dict[str, Any]:
    """Retrieve operational metrics and stats for hospital dashboard (Admin only)."""
    total_appointments = db.query(Appointment).count()
    booked_appointments = db.query(Appointment).filter(Appointment.status.in_(["booked", "confirmed"])).count()
    cancelled_appointments = db.query(Appointment).filter(Appointment.status == "cancelled").count()
    total_doctors = db.query(Doctor).filter(Doctor.is_active == True).count()
    total_specialties = db.query(Specialty).filter(Specialty.is_active == True).count()
    total_patients = db.query(Patient).count()
    pending_handoffs = db.query(HumanHandoff).filter(HumanHandoff.status == "pending").count()
    total_notifications = db.query(Notification).count()

    return {
        "total_appointments": total_appointments,
        "active_bookings": booked_appointments,
        "cancelled_appointments": cancelled_appointments,
        "active_doctors": total_doctors,
        "active_specialties": total_specialties,
        "registered_patients": total_patients,
        "pending_human_handoffs": pending_handoffs,
        "notifications_logged": total_notifications
    }


@router.get("/appointments")
def get_admin_appointments(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Retrieve detailed appointments list for administration."""
    appts = AppointmentService.get_appointments_list(
        db=db,
        status_filter=status_filter,
        limit=limit,
        offset=offset
    )
    return [AppointmentService.to_appointment_response(a) for a in appts]


@router.get("/notifications")
def get_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """View logged email notifications and delivery status (Admin only)."""
    logs = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "appointment_id": n.appointment_id,
            "recipient": n.recipient,
            "notification_type": n.notification_type,
            "status": n.status,
            "error_message": n.error_message,
            "sent_at": n.sent_at,
            "created_at": n.created_at
        }
        for n in logs
    ]


@router.get("/handoffs")
def get_human_handoff_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """View all patient human assistance requests (Admin only)."""
    query = db.query(HumanHandoff)
    if status_filter:
        query = query.filter(HumanHandoff.status == status_filter)
    handoffs = query.order_by(HumanHandoff.created_at.desc()).all()
    return [
        {
            "id": h.id,
            "session_id": h.session_id,
            "reason": h.reason,
            "patient_contact": h.patient_contact,
            "status": h.status,
            "created_at": h.created_at
        }
        for h in handoffs
    ]


@router.post("/appointments/{appointment_id}/no-show")
def mark_no_show(
    appointment_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Mark an appointment as no-show (Admin only)."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    appt.status = "no_show"
    db.commit()
    return {"success": True, "message": f"Appointment {appt.reference} marked as no_show"}


@router.post("/jobs/run-reminders")
def trigger_all_reminders(admin: AdminUser = Depends(get_current_admin)):
    """Manually trigger both 24h and 2h appointment reminder jobs (Admin only)."""
    e24, s24 = run_24h_reminders()
    e2, s2 = run_2h_reminders()
    return {
        "success": True,
        "reminder_24h": {"eligible": e24, "sent": s24},
        "reminder_2h": {"eligible": e2, "sent": s2}
    }


@router.post("/jobs/run-24h-reminders")
def trigger_24h_reminders(admin: AdminUser = Depends(get_current_admin)):
    """Manually trigger 24-hour reminder job (Admin only)."""
    eligible, sent = run_24h_reminders()
    return {"success": True, "eligible": eligible, "sent": sent}


@router.post("/jobs/run-2h-reminders")
def trigger_2h_reminders(admin: AdminUser = Depends(get_current_admin)):
    """Manually trigger 2-hour reminder job (Admin only)."""
    eligible, sent = run_2h_reminders()
    return {"success": True, "eligible": eligible, "sent": sent}

