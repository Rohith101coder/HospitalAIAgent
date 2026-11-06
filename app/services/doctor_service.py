from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.specialty import Specialty
from app.models.doctor import Doctor
from app.schemas.specialty import SpecialtyCreate, SpecialtyUpdate
from app.schemas.doctor import DoctorCreate, DoctorUpdate


class DoctorService:

    @staticmethod
    def create_specialty(db: Session, data: SpecialtyCreate) -> Specialty:
        existing = db.query(Specialty).filter(Specialty.name.ilike(data.name)).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specialty with name '{data.name}' already exists."
            )
        specialty = Specialty(
            name=data.name,
            description=data.description,
            is_active=True
        )
        db.add(specialty)
        db.commit()
        db.refresh(specialty)
        return specialty

    @staticmethod
    def get_specialties(db: Session, active_only: bool = True) -> List[Specialty]:
        query = db.query(Specialty)
        if active_only:
            query = query.filter(Specialty.is_active == True)
        return query.order_by(Specialty.name).all()

    @staticmethod
    def get_specialty_by_id(db: Session, specialty_id: int) -> Specialty:
        specialty = db.query(Specialty).filter(Specialty.id == specialty_id).first()
        if not specialty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Specialty with id {specialty_id} not found."
            )
        return specialty

    @staticmethod
    def update_specialty(db: Session, specialty_id: int, data: SpecialtyUpdate) -> Specialty:
        specialty = DoctorService.get_specialty_by_id(db, specialty_id)
        if data.name is not None and data.name.lower() != specialty.name.lower():
            existing = db.query(Specialty).filter(Specialty.name.ilike(data.name)).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Specialty with name '{data.name}' already exists."
                )
            specialty.name = data.name

        if data.description is not None:
            specialty.description = data.description
        if data.is_active is not None:
            specialty.is_active = data.is_active

        db.commit()
        db.refresh(specialty)
        return specialty

    @staticmethod
    def deactivate_specialty(db: Session, specialty_id: int) -> Specialty:
        specialty = DoctorService.get_specialty_by_id(db, specialty_id)
        specialty.is_active = False
        db.commit()
        db.refresh(specialty)
        return specialty

    @staticmethod
    def create_doctor(db: Session, data: DoctorCreate) -> Doctor:
        # Check specialty exists
        DoctorService.get_specialty_by_id(db, data.specialty_id)
        doctor = Doctor(
            name=data.name,
            specialty_id=data.specialty_id,
            qualification=data.qualification,
            experience_years=data.experience_years,
            languages=data.languages,
            consultation_fee=data.consultation_fee,
            description=data.description,
            is_active=True
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)
        return doctor

    @staticmethod
    def get_doctors(db: Session, active_only: bool = True) -> List[Doctor]:
        query = db.query(Doctor)
        if active_only:
            query = query.filter(Doctor.is_active == True)
        return query.order_by(Doctor.name).all()

    @staticmethod
    def get_doctor_by_id(db: Session, doctor_id: int) -> Doctor:
        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with id {doctor_id} not found."
            )
        return doctor

    @staticmethod
    def update_doctor(db: Session, doctor_id: int, data: DoctorUpdate) -> Doctor:
        doctor = DoctorService.get_doctor_by_id(db, doctor_id)
        if data.specialty_id is not None:
            DoctorService.get_specialty_by_id(db, data.specialty_id)
            doctor.specialty_id = data.specialty_id
        if data.name is not None:
            doctor.name = data.name
        if data.qualification is not None:
            doctor.qualification = data.qualification
        if data.experience_years is not None:
            doctor.experience_years = data.experience_years
        if data.languages is not None:
            doctor.languages = data.languages
        if data.consultation_fee is not None:
            doctor.consultation_fee = data.consultation_fee
        if data.description is not None:
            doctor.description = data.description
        if data.is_active is not None:
            doctor.is_active = data.is_active

        db.commit()
        db.refresh(doctor)
        return doctor

    @staticmethod
    def deactivate_doctor(db: Session, doctor_id: int) -> Doctor:
        doctor = DoctorService.get_doctor_by_id(db, doctor_id)
        doctor.is_active = False
        db.commit()
        db.refresh(doctor)
        return doctor

    @staticmethod
    def search_doctors_by_specialty(db: Session, specialty_name: str) -> List[Doctor]:
        """Search active doctors whose specialty name matches query (case-insensitive substring)."""
        clean_name = specialty_name.strip()
        doctors = (
            db.query(Doctor)
            .join(Specialty, Doctor.specialty_id == Specialty.id)
            .filter(
                Doctor.is_active == True,
                Specialty.is_active == True,
                Specialty.name.ilike(f"%{clean_name}%")
            )
            .order_by(Doctor.experience_years.desc())
            .all()
        )
        return doctors

