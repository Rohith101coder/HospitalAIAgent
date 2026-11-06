from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.schemas.specialty import SpecialtyCreate, SpecialtyUpdate, SpecialtyResponse
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/api/specialties", tags=["Specialties"])


@router.post("", response_model=SpecialtyResponse, status_code=status.HTTP_201_CREATED)
def create_specialty(
    data: SpecialtyCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Create a new hospital specialty (Admin only)."""
    return DoctorService.create_specialty(db, data)


@router.get("", response_model=List[SpecialtyResponse])
def get_specialties(active_only: bool = True, db: Session = Depends(get_db)):
    """List all hospital specialties."""
    return DoctorService.get_specialties(db, active_only=active_only)


@router.get("/{specialty_id}", response_model=SpecialtyResponse)
def get_specialty(specialty_id: int, db: Session = Depends(get_db)):
    """Get specialty details by ID."""
    return DoctorService.get_specialty_by_id(db, specialty_id)


@router.put("/{specialty_id}", response_model=SpecialtyResponse)
def update_specialty(
    specialty_id: int,
    data: SpecialtyUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Update specialty information (Admin only)."""
    return DoctorService.update_specialty(db, specialty_id, data)


@router.delete("/{specialty_id}", response_model=SpecialtyResponse)
def delete_specialty(
    specialty_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Deactivate a specialty (Admin only)."""
    return DoctorService.deactivate_specialty(db, specialty_id)

