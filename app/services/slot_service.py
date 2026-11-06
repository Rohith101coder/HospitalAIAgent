from datetime import datetime, date, time, timedelta
from typing import List, Optional
import pytz
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.doctor import Doctor
from app.models.schedule import DoctorSchedule, DoctorScheduleException
from app.models.slot import DoctorSlot
from app.schemas.schedule import DoctorScheduleCreate, DoctorScheduleUpdate, DoctorScheduleExceptionCreate
from app.utils.datetime_utils import get_hospital_tz, to_hospital_tz, now_utc, format_slot_time, format_date_str


class SlotService:

    @staticmethod
    def create_schedule(db: Session, data: DoctorScheduleCreate) -> DoctorSchedule:
        doctor = db.query(Doctor).filter(Doctor.id == data.doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        if data.start_time >= data.end_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time must be earlier than end_time")

        schedule = DoctorSchedule(
            doctor_id=data.doctor_id,
            weekday=data.weekday,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_duration_minutes=data.slot_duration_minutes,
            is_active=True
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def get_doctor_schedules(db: Session, doctor_id: int) -> List[DoctorSchedule]:
        return db.query(DoctorSchedule).filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.is_active == True
        ).order_by(DoctorSchedule.weekday, DoctorSchedule.start_time).all()

    @staticmethod
    def update_schedule(db: Session, schedule_id: int, data: DoctorScheduleUpdate) -> DoctorSchedule:
        sched = db.query(DoctorSchedule).filter(DoctorSchedule.id == schedule_id).first()
        if not sched:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

        if data.weekday is not None:
            sched.weekday = data.weekday
        if data.start_time is not None:
            sched.start_time = data.start_time
        if data.end_time is not None:
            sched.end_time = data.end_time
        if data.slot_duration_minutes is not None:
            sched.slot_duration_minutes = data.slot_duration_minutes
        if data.is_active is not None:
            sched.is_active = data.is_active

        if sched.start_time >= sched.end_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time must be earlier than end_time")

        db.commit()
        db.refresh(sched)
        return sched

    @staticmethod
    def delete_schedule(db: Session, schedule_id: int) -> None:
        sched = db.query(DoctorSchedule).filter(DoctorSchedule.id == schedule_id).first()
        if not sched:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
        sched.is_active = False
        db.commit()

    @staticmethod
    def create_schedule_exception(db: Session, data: DoctorScheduleExceptionCreate) -> DoctorScheduleException:
        doctor = db.query(Doctor).filter(Doctor.id == data.doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        exception = DoctorScheduleException(
            doctor_id=data.doctor_id,
            exception_date=data.exception_date,
            exception_type=data.exception_type,
            start_time=data.start_time,
            end_time=data.end_time,
            reason=data.reason
        )
        db.add(exception)
        db.commit()
        db.refresh(exception)
        return exception

    @staticmethod
    def generate_slots(db: Session, doctor_id: int, start_date: date, end_date: date) -> int:
        """
        Generates appointment slots between start_date and end_date (inclusive).
        Honors weekly schedules, holidays, leaves, modified hours, and never overwrites booked slots.
        """
        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor or not doctor.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is not found or inactive")

        if start_date > end_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date cannot be after end_date")

        tz = get_hospital_tz()
        generated_count = 0
        current_date = start_date

        while current_date <= end_date:
            # Check exceptions for this date
            exceptions = db.query(DoctorScheduleException).filter(
                DoctorScheduleException.doctor_id == doctor_id,
                DoctorScheduleException.exception_date == current_date
            ).all()

            is_holiday_or_leave = any(e.exception_type in ["holiday", "leave"] for e in exceptions)
            if is_holiday_or_leave:
                current_date += timedelta(days=1)
                continue

            # Check for modified working hours
            modified_hour_ex = next((e for e in exceptions if e.exception_type == "modified_hours"), None)

            if modified_hour_ex and modified_hour_ex.start_time and modified_hour_ex.end_time:
                # Use modified hours
                active_windows = [(modified_hour_ex.start_time, modified_hour_ex.end_time, 30)]
            else:
                # Use recurring schedule for weekday
                weekday = current_date.weekday()
                schedules = db.query(DoctorSchedule).filter(
                    DoctorSchedule.doctor_id == doctor_id,
                    DoctorSchedule.weekday == weekday,
                    DoctorSchedule.is_active == True
                ).all()
                active_windows = [(s.start_time, s.end_time, s.slot_duration_minutes) for s in schedules]

            for win_start, win_end, duration_mins in active_windows:
                slot_duration = timedelta(minutes=duration_mins)
                cur_time = win_start

                while True:
                    local_slot_start = tz.localize(datetime.combine(current_date, cur_time))
                    local_slot_end = local_slot_start + slot_duration
                    window_end_dt = tz.localize(datetime.combine(current_date, win_end))

                    if local_slot_end > window_end_dt:
                        break

                    utc_slot_start = local_slot_start.astimezone(pytz.utc).replace(tzinfo=None)
                    utc_slot_end = local_slot_end.astimezone(pytz.utc).replace(tzinfo=None)

                    # Check if slot already exists
                    existing = db.query(DoctorSlot).filter(
                        DoctorSlot.doctor_id == doctor_id,
                        DoctorSlot.start_time == utc_slot_start
                    ).first()

                    if not existing:
                        new_slot = DoctorSlot(
                            doctor_id=doctor_id,
                            start_time=utc_slot_start,
                            end_time=utc_slot_end,
                            status="available"
                        )
                        db.add(new_slot)
                        generated_count += 1

                    # Next slot time
                    cur_time = (datetime.combine(date.min, cur_time) + slot_duration).time()

            current_date += timedelta(days=1)

        db.commit()
        return generated_count

    @staticmethod
    def block_slot(db: Session, slot_id: int) -> DoctorSlot:
        slot = db.query(DoctorSlot).filter(DoctorSlot.id == slot_id).first()
        if not slot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
        if slot.status == "booked":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block an already booked slot")

        slot.status = "blocked"
        db.commit()
        db.refresh(slot)
        return slot

    @staticmethod
    def get_slots_by_doctor_and_date(
        db: Session,
        doctor_id: int,
        target_date: date,
        available_only: bool = True
    ) -> List[dict]:
        """Get slots for doctor on a specific hospital local date."""
        tz = get_hospital_tz()
        start_of_day = tz.localize(datetime.combine(target_date, time.min))
        end_of_day = tz.localize(datetime.combine(target_date, time.max))

        utc_start = start_of_day.astimezone(pytz.utc).replace(tzinfo=None)
        utc_end = end_of_day.astimezone(pytz.utc).replace(tzinfo=None)

        query = db.query(DoctorSlot).filter(
            DoctorSlot.doctor_id == doctor_id,
            DoctorSlot.start_time >= utc_start,
            DoctorSlot.start_time <= utc_end
        )

        if available_only:
            query = query.filter(
                DoctorSlot.status == "available",
                DoctorSlot.start_time > now_utc()  # only future slots
            )

        slots = query.order_by(DoctorSlot.start_time).all()

        results = []
        for s in slots:
            results.append({
                "id": s.id,
                "doctor_id": s.doctor_id,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "status": s.status,
                "display_time": format_slot_time(s.start_time, s.end_time),
                "display_date": format_date_str(s.start_time)
            })
        return results

