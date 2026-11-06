from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.schemas.doctor import DoctorCreate, DoctorUpdate, DoctorResponse, SlotResponse
from app.services.doctor_service import DoctorService
from app.services.slot_service import SlotService

router = APIRouter(prefix="/api/doctors", tags=["Doctors"])


@router.post("", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def create_doctor(
    data: DoctorCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Register a new doctor (Admin only)."""
    doctor = DoctorService.create_doctor(db, data)
    resp = DoctorResponse.model_validate(doctor)
    resp.specialty_name = doctor.specialty.name if doctor.specialty else None
    return resp


@router.get("/search", response_model=List[DoctorResponse])
def search_doctors(
    specialty: str = Query(..., description="Specialty name to search, e.g. Cardiology"),
    db: Session = Depends(get_db)
):
    """Search active doctors by specialty name."""
    doctors = DoctorService.search_doctors_by_specialty(db, specialty)
    result = []
    for d in doctors:
        item = DoctorResponse.model_validate(d)
        item.specialty_name = d.specialty.name if d.specialty else None
        result.append(item)
    return result


@router.get("", response_model=List[DoctorResponse])
def get_doctors(active_only: bool = True, db: Session = Depends(get_db)):
    """List all active doctors."""
    doctors = DoctorService.get_doctors(db, active_only=active_only)
    result = []
    for d in doctors:
        item = DoctorResponse.model_validate(d)
        item.specialty_name = d.specialty.name if d.specialty else None
        result.append(item)
    return result


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Get doctor profile by ID."""
    doctor = DoctorService.get_doctor_by_id(db, doctor_id)
    resp = DoctorResponse.model_validate(doctor)
    resp.specialty_name = doctor.specialty.name if doctor.specialty else None
    return resp


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    data: DoctorUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Update doctor information (Admin only)."""
    doctor = DoctorService.update_doctor(db, doctor_id, data)
    resp = DoctorResponse.model_validate(doctor)
    resp.specialty_name = doctor.specialty.name if doctor.specialty else None
    return resp


@router.delete("/{doctor_id}", response_model=DoctorResponse)
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Deactivate doctor profile (Admin only)."""
    doctor = DoctorService.deactivate_doctor(db, doctor_id)
    resp = DoctorResponse.model_validate(doctor)
    resp.specialty_name = doctor.specialty.name if doctor.specialty else None
    return resp


@router.get("/{doctor_id}/slots", response_model=List[SlotResponse])
def get_doctor_slots(
    doctor_id: int,
    slot_date: date = Query(..., alias="date", description="Slot date in YYYY-MM-DD"),
    available_only: bool = True,
    db: Session = Depends(get_db)
):
    """Retrieve available appointment slots for a doctor on a specific date."""
    slots = SlotService.get_slots_by_doctor_and_date(
        db=db,
        doctor_id=doctor_id,
        target_date=slot_date,
        available_only=available_only
    )
    return slots

