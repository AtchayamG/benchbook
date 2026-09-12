"""Benchbook Realistic Seed Data for Tamil Nadu Repair Shop Context.

Provides contact-safe synthetic sample jobs, technician notes, parts, and estimates
for quick demonstrations and testing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict
from uuid import uuid4

from benchbook.domain.models import Job, JobState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class PresetData(TypedDict):
    customer_name: str
    customer_phone: str
    customer_address: str
    device_kind: str
    brand_model: str
    serial_number: str
    intake_symptoms: str
    physical_condition: str
    accessories_received: list[str]
    promised_date: str
    assigned_technician: str


SAMPLE_PRESETS: list[PresetData] = [
    {
        "customer_name": "Senthil Nathan",
        "customer_phone": "+91 98401 23456",
        "customer_address": "14/2 Cross Cut Road, Gandhipuram, Coimbatore 641012",
        "device_kind": "BLDC Ceiling Fan",
        "brand_model": "Atomberg Renesa 1200mm Smart",
        "serial_number": "ATMB-2024-88419",
        "intake_symptoms": (
            "Motor humming loudly at speed 2, erratic speed transitions, "
            "LED blinks 3 times and stops."
        ),
        "physical_condition": "Blade bracket intact, slight dust on canopy housing, remote included.",
        "accessories_received": ["Remote Control", "Downrod Shackle Kit"],
        "promised_date": "2026-09-15",
        "assigned_technician": "Murugan R.",
    },
    {
        "customer_name": "Meenakshi Sundaram",
        "customer_phone": "+91 94432 34567",
        "customer_address": "88 Thiruvenkatasamy Road, RS Puram, Coimbatore 641002",
        "device_kind": "Split AC Inverter PCB",
        "brand_model": "Voltas 185V Vectra 1.5 Ton Inverter",
        "serial_number": "VLT-PCB-99210",
        "intake_symptoms": (
            "Outdoor unit fan runs for 20 seconds, compressor does not start, "
            "display shows E6 error code."
        ),
        "physical_condition": "PCB board removed by customer AC mechanic; heatsink thermal paste dried out.",
        "accessories_received": ["Outdoor Main PCB", "Ambient Temp Sensor Probe"],
        "promised_date": "2026-09-14",
        "assigned_technician": "Palanisamy K.",
    },
    {
        "customer_name": "Anitha Selvaraj",
        "customer_phone": "+91 97890 45678",
        "customer_address": "45 Avinashi Road, Peelamedu, Coimbatore 641004",
        "device_kind": "Mixer Grinder",
        "brand_model": "Preethi Zodiac 750W",
        "serial_number": "PZ-750-44912",
        "intake_symptoms": (
            "Strong burning smell from base, high sparking seen through bottom vents, "
            "red overload reset button popped."
        ),
        "physical_condition": "Jar couplers normal, base body has light masala stains, power cord good.",
        "accessories_received": ["1.5L Master Chef Jar", "Power Cord Base"],
        "promised_date": "2026-09-13",
        "assigned_technician": "Murugan R.",
    },
    {
        "customer_name": "Dr. R. Balaji",
        "customer_phone": "+91 94860 67890",
        "customer_address": "12 Sengupta Street, Ramnagar, Coimbatore 641009",
        "device_kind": "Laptop",
        "brand_model": "Lenovo ThinkPad E14 Gen 4 AMD",
        "serial_number": "PF-3X992A",
        "intake_symptoms": (
            "USB-C charging port loose, battery not charging, "
            "right display hinge stiff and cracking top palmrest."
        ),
        "physical_condition": "Top cover minor scuffs, right corner bezel separated, charger adapter included.",
        "accessories_received": ["65W USB-C Adapter", "Laptop Sleeve"],
        "promised_date": "2026-09-16",
        "assigned_technician": "Karthik Rajan",
    },
]


def create_sample_job(index: int = 0) -> Job:
    """Create a domain Job object from a preset."""
    preset = SAMPLE_PRESETS[index % len(SAMPLE_PRESETS)]
    now = _now_iso()
    return Job(
        job_id=str(uuid4()),
        job_number=f"BB-2026-{101 + index:03d}",
        customer_name=preset["customer_name"],
        customer_phone=preset["customer_phone"],
        customer_address=preset["customer_address"],
        device_kind=preset["device_kind"],
        brand_model=preset["brand_model"],
        serial_number=preset["serial_number"],
        intake_symptoms=preset["intake_symptoms"],
        physical_condition=preset["physical_condition"],
        accessories_received=list(preset["accessories_received"]),
        promised_date=preset["promised_date"],
        assigned_technician=preset["assigned_technician"],
        current_state=JobState.INTAKE,
        version=1,
        created_at=now,
        updated_at=now,
    )
