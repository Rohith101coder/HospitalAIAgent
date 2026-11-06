import secrets
from datetime import datetime


def generate_appointment_reference() -> str:
    """Generate a unique human-friendly booking reference: MED-YYYY-XXXXX."""
    year = datetime.utcnow().year
    random_part = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
    return f"MED-{year}-{random_part}"

