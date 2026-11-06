from datetime import datetime, date, time
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DoctorScheduleBase(BaseModel):
    doctor_id: int
    weekday: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(30, ge=10, le=120)


class DoctorScheduleCreate(DoctorScheduleBase):
    pass


class DoctorScheduleUpdate(BaseModel):
    weekday: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=10, le=120)
    is_active: Optional[bool] = None


class DoctorScheduleResponse(DoctorScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class DoctorScheduleExceptionCreate(BaseModel):
    doctor_id: int
    exception_date: date
    exception_type: str = Field(..., description="holiday, leave, modified_hours")
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = None


class DoctorScheduleExceptionResponse(DoctorScheduleExceptionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime



class GenerateSlotsRequest(BaseModel):
    doctor_id: int
    start_date: date
    end_date: date


class GenerateSlotsResponse(BaseModel):
    doctor_id: int
    start_date: date
    end_date: date
    generated_count: int
    message: str


class BlockSlotResponse(BaseModel):
    slot_id: int
    status: str
    message: str
