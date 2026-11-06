import uuid
import json
from app.agent.agent import HospitalAgent
from app.agent.tool_executor import ToolExecutor
from app.agent.tools import get_tools


def test_agent_tools_initialization(db_session):
    agent = HospitalAgent(db=db_session)
    assert len(agent.tools) == 11
    tool_names = [t.name for t in agent.tools]
    expected_tools = [
        "find_doctors",
        "get_doctor_details",
        "get_available_slots",
        "initiate_booking",
        "request_appointment_otp",
        "verify_appointment_otp",
        "confirm_booking",
        "get_my_appointments",
        "cancel_appointment",
        "reschedule_appointment",
        "request_human_handoff"
    ]
    for et in expected_tools:
        assert et in tool_names


def test_tool_executor_find_doctors(db_session):
    executor = ToolExecutor(db=db_session)
    result = executor.find_doctors("Cardiology")
    assert result["success"] is True
    assert len(result["doctors"]) >= 1
    assert result["doctors"][0]["specialty"] == "Cardiology"


def test_tool_executor_available_slots(db_session):
    executor = ToolExecutor(db=db_session)
    # Find a doctor
    doc_res = executor.find_doctors("Cardiology")
    doctor_id = doc_res["doctors"][0]["doctor_id"]

    from datetime import date, timedelta
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    slots_res = executor.get_available_slots(doctor_id, tomorrow)
    assert slots_res["success"] is True
    assert "available_slots" in slots_res


def test_tool_executor_unknown_tool_and_invalid_args(db_session):
    executor = ToolExecutor(db=db_session)
    # Invalid date
    bad_date_res = executor.get_available_slots(1, "invalid-date-string")
    assert bad_date_res["success"] is False
    assert "Invalid date format" in bad_date_res["error"]
