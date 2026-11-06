"""
Seed script for MediDesk Agent database.
Initializes tables and seeds initial admin, specialties, doctors, schedules,
slots for the next 7 days, patients, and sample appointments.
Completely idempotent.
"""
import sys
from datetime import datetime, date, time, timedelta
import pytz
from sqlalchemy import text
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.admin import AdminUser
from app.models.patient import Patient
from app.models.specialty import Specialty
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule, DoctorScheduleException
from app.models.slot import DoctorSlot
from app.models.appointment import Appointment
from app.models.appointment_history import AppointmentHistory
from app.utils.datetime_utils import get_hospital_tz, hospital_to_utc, now_hospital


def ensure_database_exists():
    """Ensure medibook database exists when running against MySQL / TiDB."""
    if settings.DATABASE_URL and settings.DATABASE_URL.startswith("sqlite"):
        return

    # In TiDB Cloud, the cluster already provisions the database (e.g. medibook)
    if "tidbcloud.com" in settings.DB_HOST or settings.DB_PORT == 4000:
        return

    # PyMySQL connection to local MySQL server root to create medibook database if not present
    try:
        import pymysql
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            charset="utf8mb4",
        )
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        conn.close()
        print(f"Database `{settings.DB_NAME}` verified/created successfully.")
    except Exception as e:
        print(f"Database pre-check notice (might already exist or direct URL): {e}")


def seed():
    ensure_database_exists()
    print("Creating database tables if not existing...")
    Base.metadata.create_all(bind=engine)
    print("Tables initialized.")

    db = SessionLocal()
    try:
        # 1. Admin User
        admin_email = settings.ADMIN_EMAIL
        admin = db.query(AdminUser).filter(AdminUser.email == admin_email).first()
        if not admin:
            admin = AdminUser(
                name="Hospital Super Admin",
                email=admin_email,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                is_active=True
            )
            db.add(admin)
            db.commit()
            print(f"Seeded Admin User: {admin_email}", flush=True)
        else:
            admin.password_hash = hash_password(settings.ADMIN_PASSWORD)
            db.commit()
            print(f"Admin User {admin_email} synced with current password.", flush=True)

        # 2. Specialties (7 required)
        specialties_data = [
            ("Cardiology", "Diagnosis and treatment of heart defects, coronary artery disease, heart failure, and valvular heart disease."),
            ("Neurology", "Specialized care for disorders of the brain, spinal cord, nerves, and muscles."),
            ("Orthopedics", "Diagnosis, treatment, and surgery for musculoskeletal system, bones, joints, ligaments, and tendons."),
            ("Pediatrics", "Comprehensive medical care for infants, children, and adolescents."),
            ("Dermatology", "Expert diagnosis and care for skin, hair, nail conditions, and cosmetic disorders."),
            ("General Medicine", "Primary healthcare, diagnosis of acute and chronic adult illnesses, and preventive health."),
            ("Gynecology", "Specialized healthcare for female reproductive system, pregnancy, and maternal wellness."),
        ]

        specialty_map = {}
        for name, desc in specialties_data:
            spec = db.query(Specialty).filter(Specialty.name == name).first()
            if not spec:
                spec = Specialty(name=name, description=desc, is_active=True)
                db.add(spec)
                db.commit()
                db.refresh(spec)
                print(f"Seeded Specialty: {name}")
            specialty_map[name] = spec

        # 3. Fictional Doctors (At least 6 fictional doctors)
        doctors_data = [
            {
                "name": "Dr. Ramesh Sharma",
                "specialty": "Cardiology",
                "qualification": "MBBS, MD, DM (Cardiology)",
                "experience_years": 15,
                "languages": ["English", "Hindi", "Telugu"],
                "consultation_fee": 800.00,
                "description": "Senior Consultant Interventional Cardiologist specializing in preventive heart health and angioplasty."
            },
            {
                "name": "Dr. Ananya Reddy",
                "specialty": "Neurology",
                "qualification": "MBBS, MD, DM (Neurology)",
                "experience_years": 12,
                "languages": ["Telugu", "English"],
                "consultation_fee": 900.00,
                "description": "Expert Neurologist focusing on migraine management, stroke rehabilitation, and epilepsy care."
            },
            {
                "name": "Dr. Vikram Joshi",
                "specialty": "Orthopedics",
                "qualification": "MBBS, MS (Orthopedics), M.Ch",
                "experience_years": 14,
                "languages": ["English", "Hindi"],
                "consultation_fee": 750.00,
                "description": "Orthopedic surgeon specializing in joint replacement, arthroscopy, and sports injuries."
            },
            {
                "name": "Dr. Priya Rao",
                "specialty": "Pediatrics",
                "qualification": "MBBS, DCH, DNB (Pediatrics)",
                "experience_years": 10,
                "languages": ["English", "Telugu", "Hindi"],
                "consultation_fee": 600.00,
                "description": "Compassionate pediatrician experienced in newborn care, childhood immunizations, and developmental health."
            },
            {
                "name": "Dr. Sneha Verma",
                "specialty": "Dermatology",
                "qualification": "MBBS, MD (DVL)",
                "experience_years": 8,
                "languages": ["English", "Hindi"],
                "consultation_fee": 650.00,
                "description": "Dermatologist and aesthetic specialist focusing on chronic skin diseases, acne, and hair therapy."
            },
            {
                "name": "Dr. Rajeshwar Naidu",
                "specialty": "General Medicine",
                "qualification": "MBBS, MD (General Medicine)",
                "experience_years": 18,
                "languages": ["Telugu", "English"],
                "consultation_fee": 500.00,
                "description": "Senior physician dealing with diabetes management, hypertension, seasonal fevers, and comprehensive health checks."
            },
            {
                "name": "Dr. Sunita Kulkarni",
                "specialty": "Gynecology",
                "qualification": "MBBS, MS (OBG), FICOG",
                "experience_years": 16,
                "languages": ["English", "Hindi", "Telugu"],
                "consultation_fee": 850.00,
                "description": "Obstetrician and Gynecologist with extensive experience in high-risk pregnancies and laparoscopic surgeries."
            }
        ]

        doctor_map = {}
        for doc_info in doctors_data:
            spec = specialty_map[doc_info["specialty"]]
            doc = db.query(Doctor).filter(Doctor.name == doc_info["name"]).first()
            if not doc:
                doc = Doctor(
                    name=doc_info["name"],
                    specialty_id=spec.id,
                    qualification=doc_info["qualification"],
                    experience_years=doc_info["experience_years"],
                    languages=doc_info["languages"],
                    consultation_fee=doc_info["consultation_fee"],
                    description=doc_info["description"],
                    is_active=True
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                print(f"Seeded Doctor: {doc.name} ({spec.name})")
            doctor_map[doc.name] = doc

        # 4. Doctor Recurring Schedules
        # Example: Monday to Saturday morning or afternoon slots
        for doc_name, doc in doctor_map.items():
            existing_schedules = db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doc.id).count()
            if existing_schedules == 0:
                # Mon-Fri 09:00 - 13:00
                for weekday in range(0, 5):  # Mon-Fri
                    sched1 = DoctorSchedule(
                        doctor_id=doc.id,
                        weekday=weekday,
                        start_time=time(9, 0),
                        end_time=time(13, 0),
                        slot_duration_minutes=30,
                        is_active=True
                    )
                    db.add(sched1)
                # Sat 14:00 - 18:00
                sched2 = DoctorSchedule(
                    doctor_id=doc.id,
                    weekday=5,
                    start_time=time(14, 0),
                    end_time=time(18, 0),
                    slot_duration_minutes=30,
                    is_active=True
                )
                db.add(sched2)
                db.commit()
                print(f"Configured weekly schedule for {doc_name}")

        # 5. Generate slots for the next 7 days in Asia/Kolkata timezone
        tz = get_hospital_tz()
        today = now_hospital().date()

        # Preload existing slots in memory to avoid repetitive WAN queries
        existing_slots = set(
            db.query(DoctorSlot.doctor_id, DoctorSlot.start_time).all()
        )
        new_slots = []

        for day_offset in range(1, 8):  # Next 7 days
            target_date = today + timedelta(days=day_offset)
            target_weekday = target_date.weekday()

            for doc in doctor_map.values():
                schedules = db.query(DoctorSchedule).filter(
                    DoctorSchedule.doctor_id == doc.id,
                    DoctorSchedule.weekday == target_weekday,
                    DoctorSchedule.is_active == True
                ).all()

                for sched in schedules:
                    slot_duration = timedelta(minutes=sched.slot_duration_minutes)
                    current_start_time = sched.start_time

                    while True:
                        # Combine date with time in hospital timezone
                        local_slot_start = tz.localize(datetime.combine(target_date, current_start_time))
                        local_slot_end = local_slot_start + slot_duration
                        
                        # Stop if end time exceeds schedule
                        schedule_end_dt = tz.localize(datetime.combine(target_date, sched.end_time))
                        if local_slot_end > schedule_end_dt:
                            break

                        # Convert to UTC for DB storage
                        utc_slot_start = local_slot_start.astimezone(pytz.utc).replace(tzinfo=None)
                        utc_slot_end = local_slot_end.astimezone(pytz.utc).replace(tzinfo=None)

                        if (doc.id, utc_slot_start) not in existing_slots:
                            new_slot = DoctorSlot(
                                doctor_id=doc.id,
                                start_time=utc_slot_start,
                                end_time=utc_slot_end,
                                status="available"
                            )
                            new_slots.append(new_slot)
                            existing_slots.add((doc.id, utc_slot_start))

                        # Advance
                        next_dt = (datetime.combine(date.min, current_start_time) + slot_duration).time()
                        current_start_time = next_dt

        if new_slots:
            db.add_all(new_slots)
            db.commit()
            print(f"Generated {len(new_slots)} doctor slots for next 7 days.", flush=True)
        else:
            print("Doctor slots for next 7 days already exist.", flush=True)


        # 6. Fictional Patients
        patients_data = [
            {"full_name": "Karthik Subramanian", "email": "karthik.subramanian@example.com", "phone": "+919876543210"},
            {"full_name": "Lakshmi Narayana", "email": "lakshmi.narayana@example.com", "phone": "+919848012345"},
            {"full_name": "Rohan Gupta", "email": "rohan.gupta@example.com", "phone": "+919911223344"},
        ]

        patient_map = {}
        for p_info in patients_data:
            p = db.query(Patient).filter(Patient.email == p_info["email"]).first()
            if not p:
                p = Patient(
                    full_name=p_info["full_name"],
                    email=p_info["email"],
                    phone=p_info["phone"]
                )
                db.add(p)
                db.commit()
                db.refresh(p)
                print(f"Seeded Patient: {p.full_name}")
            patient_map[p.email] = p

        # 7. Sample Appointments
        doc1 = doctor_map["Dr. Ramesh Sharma"]
        pat1 = patient_map["karthik.subramanian@example.com"]
        existing_appts = db.query(Appointment).filter(Appointment.patient_id == pat1.id).count()

        if existing_appts == 0:
            # Find an available slot for doc1
            slot = db.query(DoctorSlot).filter(
                DoctorSlot.doctor_id == doc1.id,
                DoctorSlot.status == "available"
            ).first()

            if slot:
                slot.status = "booked"
                sample_ref = "MED-2026-DEMO1"
                appt = Appointment(
                    reference=sample_ref,
                    patient_id=pat1.id,
                    doctor_id=doc1.id,
                    slot_id=slot.id,
                    status="confirmed",
                    reason="Routine heart checkup and blood pressure assessment"
                )
                db.add(appt)
                db.flush()

                history = AppointmentHistory(
                    appointment_id=appt.id,
                    old_slot_id=None,
                    new_slot_id=slot.id,
                    action="booked",
                    changed_by="patient"
                )
                db.add(history)
                db.commit()
                print(f"Seeded sample appointment: {sample_ref}")

        print("Database seeding completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

