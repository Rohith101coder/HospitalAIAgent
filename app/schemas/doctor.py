from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


class DoctorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    specialty_id: int
    qualification: str = Field(..., min_length=2, max_length=100)
    experience_years: int = Field(0, ge=0)
    languages: List[str] = Field(default_factory=list)
    consultation_fee: Decimal = Field(..., ge=0)
    description: Optional[str] = None


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    specialty_id: Optional[int] = None
    qualification: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0)
    languages: Optional[List[str]] = None
    consultation_fee: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DoctorResponse(DoctorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    specialty_name: Optional[str] = None


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: str
    display_time: Optional[str] = None
    display_date: Optional[str] = None

