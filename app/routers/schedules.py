from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.schemas.schedule import (
    DoctorScheduleCreate,
    DoctorScheduleUpdate,
    DoctorScheduleResponse,
    DoctorScheduleExceptionCreate,
    DoctorScheduleExceptionResponse,
    GenerateSlotsRequest,
    GenerateSlotsResponse,
    BlockSlotResponse
)
from app.services.slot_service import SlotService

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])


@router.post("", response_model=DoctorScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: DoctorScheduleCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Add a recurring weekly schedule for a doctor (Admin only)."""
    return SlotService.create_schedule(db, data)


@router.get("/doctor/{doctor_id}", response_model=List[DoctorScheduleResponse])
def get_doctor_schedules(
    doctor_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Get all recurring schedules for a doctor (Admin only)."""
    return SlotService.get_doctor_schedules(db, doctor_id)


@router.put("/{schedule_id}", response_model=DoctorScheduleResponse)
def update_schedule(
    schedule_id: int,
    data: DoctorScheduleUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Update recurring schedule (Admin only)."""
    return SlotService.update_schedule(db, schedule_id, data)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Deactivate a recurring schedule (Admin only)."""
    SlotService.delete_schedule(db, schedule_id)
    return None


@router.post("/exceptions", response_model=DoctorScheduleExceptionResponse, status_code=status.HTTP_201_CREATED)
def create_exception(
    data: DoctorScheduleExceptionCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Configure doctor holiday, leave, or modified working hours (Admin only)."""
    return SlotService.create_schedule_exception(db, data)


@router.post("/generate-slots", response_model=GenerateSlotsResponse)
def generate_slots(
    data: GenerateSlotsRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generate daily appointment slots for a date range (Admin only)."""
    count = SlotService.generate_slots(db, data.doctor_id, data.start_date, data.end_date)
    return GenerateSlotsResponse(
        doctor_id=data.doctor_id,
        start_date=data.start_date,
        end_date=data.end_date,
        generated_count=count,
        message=f"Successfully generated {count} slots."
    )


@router.post("/block-slot/{slot_id}", response_model=BlockSlotResponse)
def block_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Block an available slot from being booked (Admin only)."""
    slot = SlotService.block_slot(db, slot_id)
    return BlockSlotResponse(
        slot_id=slot.id,
        status=slot.status,
        message="Slot successfully blocked."
    )

