"""Benchbook Grounded Parts Catalogue and PII Redaction.

Enforces:
1. Stable catalogue IDs for synthetic regional parts grounding.
2. Explicit synthetic / unverified cost and availability markers.
3. Strict customer PII redaction before context is passed to advisory inference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CataloguePart:
    part_id: str
    part_name: str
    unit_cost_inr: float
    availability_status: str
    supplier_name: str
    device_kind: str
    description: str


PARTS_CATALOGUE: dict[str, CataloguePart] = {
    "FAN-BRG-608ZZ": CataloguePart(
        part_id="FAN-BRG-608ZZ",
        part_name="Deep Groove Ball Bearing 608ZZ",
        unit_cost_inr=120.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="BLDC Ceiling Fan",
        description="High-speed dual shielded ball bearing for motor hub vibration / humming.",
    ),
    "FAN-PCB-ATMB": CataloguePart(
        part_id="FAN-PCB-ATMB",
        part_name="Atomberg Renesa BLDC Motor Controller Board",
        unit_cost_inr=850.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="BLDC Ceiling Fan",
        description="Microcontroller driver board with sensorless BLDC control circuitry.",
    ),
    "FAN-WND-CU48": CataloguePart(
        part_id="FAN-WND-CU48",
        part_name="Copper Magnet Wire (0.45mm / SWG 26)",
        unit_cost_inr=350.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="BLDC Ceiling Fan",
        description="Grade-2 enameled copper stator rewinding wire spool.",
    ),
    "FAN-REM-RF24": CataloguePart(
        part_id="FAN-REM-RF24",
        part_name="2.4GHz RF Remote Unit",
        unit_cost_inr=250.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="BLDC Ceiling Fan",
        description="Pairable RF replacement remote with sleep and boost timer keys.",
    ),
    "FAN-SHA-12MM": CataloguePart(
        part_id="FAN-SHA-12MM",
        part_name="Downrod Rubber Isolation Shackle Kit (12mm)",
        unit_cost_inr=75.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="BLDC Ceiling Fan",
        description="Anti-vibration rubber damper bushing with safety split pin.",
    ),
    "FAN-CAP-25MF": CataloguePart(
        part_id="FAN-CAP-25MF",
        part_name="Metal Film Run Capacitor (2.5uF 440V)",
        unit_cost_inr=90.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="BLDC Ceiling Fan",
        description="Heavy-duty metallized polypropylene motor start/run capacitor.",
    ),
    "MIX-COUP-RUB": CataloguePart(
        part_id="MIX-COUP-RUB",
        part_name="Mixer Grinder Rubber Coupler (6-tooth)",
        unit_cost_inr=45.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="Mixer Grinder",
        description="Wear-resistant molded rubber motor-to-jar coupler with bronze insert.",
    ),
    "MIX-JAR-BLD": CataloguePart(
        part_id="MIX-JAR-BLD",
        part_name="Stainless Steel Dry Grinding Blade Assembly",
        unit_cost_inr=180.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="Mixer Grinder",
        description="Laser-sharpened SS304 multi-purpose jar blade with brass nut.",
    ),
    "MIX-CB-6X8": CataloguePart(
        part_id="MIX-CB-6X8",
        part_name="Heavy Duty Carbon Brushes 6x8mm (Pair)",
        unit_cost_inr=80.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="Mixer Grinder",
        description="High-conductivity graphite carbon brushes with tension springs.",
    ),
    "IRO-THM-10A": CataloguePart(
        part_id="IRO-THM-10A",
        part_name="Bimetallic Thermostat 10A 250V",
        unit_cost_inr=140.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="Steam Iron",
        description="Ceramic-insulated adjustable snap-action bimetal thermostat.",
    ),
    "IRO-THE-192": CataloguePart(
        part_id="IRO-THE-192",
        part_name="Thermal Cutoff Fuse (192°C 10A)",
        unit_cost_inr=40.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="Steam Iron",
        description="One-shot thermal protection fuse link for over-temperature cutoff.",
    ),
    "IRO-COR-3C": CataloguePart(
        part_id="IRO-COR-3C",
        part_name="Heavy Duty 3-Core Braided Power Cord (1.5m)",
        unit_cost_inr=160.0,
        availability_status="Sample / Unverified",
        supplier_name="Synthetic Regional Supplier",
        device_kind="Steam Iron",
        description="Heat-resistant braided textile outer sheath with molded 16A plug.",
    ),
}


_PHONE_RE = re.compile(r"(?:\+?91[\s.-]?)?[6-9]\d{9}|\b\d{10}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PAYMENT_RE = re.compile(r"\b(?:UPI|REF|TXN|PAY)[-:\s]?[A-Za-z0-9]{6,24}\b", re.IGNORECASE)

MAX_BOUNDED_STRING_LENGTH = 1000


def _scrub_text(text: Any, known_pii: list[tuple[re.Pattern[str], str]]) -> str:
    """Scrub known customer identifiers and patterns from free text, bounding length."""
    if text is None:
        return ""
    bounded = str(text)[:MAX_BOUNDED_STRING_LENGTH]
    for pattern, replacement in known_pii:
        bounded = pattern.sub(replacement, bounded)
    bounded = _PHONE_RE.sub("[REDACTED_PHONE]", bounded)
    bounded = _EMAIL_RE.sub("[REDACTED_EMAIL]", bounded)
    bounded = _PAYMENT_RE.sub("[REDACTED_PAYMENT]", bounded)
    return bounded


def redact_repair_context(raw_context: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded, allowlisted repair context and scrub all known and patterned PII."""
    known_pii: list[tuple[re.Pattern[str], str]] = []

    cust_name = raw_context.get("customer_name")
    if cust_name and isinstance(cust_name, str) and cust_name.strip():
        name_clean = cust_name.strip()
        known_pii.append((re.compile(re.escape(name_clean), re.IGNORECASE), "[REDACTED_CUSTOMER]"))
        for part in name_clean.split():
            if len(part) >= 3 and part.lower() not in (
                "fan",
                "iron",
                "mixer",
                "the",
                "and",
                "for",
                "with",
                "from",
            ):
                known_pii.append(
                    (re.compile(re.escape(part), re.IGNORECASE), "[REDACTED_CUSTOMER]")
                )

    cust_phone = raw_context.get("customer_phone")
    if cust_phone and isinstance(cust_phone, str) and cust_phone.strip():
        phone_clean = cust_phone.strip()
        known_pii.append((re.compile(re.escape(phone_clean)), "[REDACTED_PHONE]"))
        digits_only = re.sub(r"\D", "", phone_clean)
        if len(digits_only) >= 7:
            known_pii.append((re.compile(re.escape(digits_only)), "[REDACTED_PHONE]"))

    cust_addr = raw_context.get("customer_address")
    if cust_addr and isinstance(cust_addr, str) and cust_addr.strip():
        addr_clean = cust_addr.strip()
        known_pii.append((re.compile(re.escape(addr_clean), re.IGNORECASE), "[REDACTED_ADDRESS]"))
        for segment in re.split(r"[,;\n]", addr_clean):
            seg = segment.strip()
            if len(seg) >= 5 and seg.lower() not in ("tamil nadu", "coimbatore", "gandhipuram"):
                known_pii.append((re.compile(re.escape(seg), re.IGNORECASE), "[REDACTED_ADDRESS]"))

    serial = raw_context.get("serial_number")
    if serial and isinstance(serial, str) and serial.strip():
        known_pii.append(
            (re.compile(re.escape(serial.strip()), re.IGNORECASE), "[REDACTED_SERIAL]")
        )

    payment_ref = raw_context.get("payment_reference")
    if payment_ref and isinstance(payment_ref, str) and payment_ref.strip():
        known_pii.append(
            (re.compile(re.escape(payment_ref.strip()), re.IGNORECASE), "[REDACTED_PAYMENT]")
        )

    redacted: dict[str, Any] = {
        "job_id": str(raw_context.get("job_id", "")),
        "job_number": str(raw_context.get("job_number", "")),
        "customer_name": "[REDACTED_CUSTOMER]",
        "customer_phone": "[REDACTED_PHONE]",
        "customer_address": "[REDACTED_ADDRESS]",
        "serial_number": "[REDACTED_SERIAL]",
        "device_kind": str(raw_context.get("device_kind", "")),
        "brand_model": str(raw_context.get("brand_model", "")),
        "intake_symptoms": _scrub_text(raw_context.get("intake_symptoms"), known_pii),
        "physical_condition": _scrub_text(raw_context.get("physical_condition"), known_pii),
        "current_state": str(raw_context.get("current_state", "")),
        "version": raw_context.get("version", 1),
    }

    if "technician_notes" in raw_context and isinstance(raw_context["technician_notes"], list):
        redacted["technician_notes"] = [
            {
                "diagnosis_findings": _scrub_text(
                    n.get("diagnosis_findings")
                    if isinstance(n, dict)
                    else getattr(n, "diagnosis_findings", ""),
                    known_pii,
                ),
                "root_cause": _scrub_text(
                    n.get("root_cause") if isinstance(n, dict) else getattr(n, "root_cause", ""),
                    known_pii,
                ),
                "recommended_action": _scrub_text(
                    n.get("recommended_action")
                    if isinstance(n, dict)
                    else getattr(n, "recommended_action", ""),
                    known_pii,
                ),
            }
            for n in raw_context["technician_notes"][:5]
        ]

    if "estimate" in raw_context and isinstance(raw_context["estimate"], dict):
        est = raw_context["estimate"]
        redacted["estimate"] = {
            "parts_total_inr": est.get("parts_total_inr", 0.0),
            "labor_charge_inr": est.get("labor_charge_inr", 0.0),
            "total_amount_inr": est.get("total_amount_inr", 0.0),
            "promised_delivery_date": str(est.get("promised_delivery_date", "")),
        }

    # Scrub every outbound text field, including free-text device/model labels.
    for key in ("job_id", "job_number", "device_kind", "brand_model", "current_state"):
        redacted[key] = _scrub_text(redacted[key], known_pii)
    return redacted


def get_catalogue_summary() -> list[dict[str, Any]]:
    """Return synthetic parts catalogue list formatted for agent context."""
    return [
        {
            "part_id": p.part_id,
            "part_name": p.part_name,
            "unit_cost_inr": p.unit_cost_inr,
            "device_kind": p.device_kind,
            "description": p.description,
        }
        for p in PARTS_CATALOGUE.values()
    ]
