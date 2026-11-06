from typing import Optional
from sqlalchemy.orm import Session
from app.models.patient import Patient


class PatientService:
    """Service for managing patient contact records based on normalized email."""

    @staticmethod
    def normalize_email(email: str) -> str:
        """Trim whitespace and convert to lowercase."""
        return email.strip().lower() if email else ""

    @staticmethod
    def get_patient_by_email(db: Session, email: str) -> Optional[Patient]:
        """Find an existing patient contact record by normalized email."""
        clean_email = PatientService.normalize_email(email)
        return db.query(Patient).filter(Patient.normalized_email == clean_email).first()

    @staticmethod
    def get_or_create_patient(
        db: Session,
        full_name: str,
        email: str,
        phone: str
    ) -> Patient:
        """
        Find existing patient by normalized email or create a new contact record.
        Updates contact name/phone if new details are provided.
        Does NOT create passwords or user login accounts.
        """
        clean_email = PatientService.normalize_email(email)
        clean_name = full_name.strip()
        clean_phone = phone.strip()

        patient = db.query(Patient).filter(Patient.normalized_email == clean_email).first()

        if patient:
            if clean_phone:
                patient.phone = clean_phone
            if clean_name:
                patient.full_name = clean_name
            db.flush()
            return patient

        # Create new patient record
        patient = Patient(
            full_name=clean_name,
            normalized_email=clean_email,
            email=clean_email,
            phone=clean_phone
        )
        db.add(patient)
        db.flush()
        return patient
