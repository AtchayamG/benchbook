"""Benchbook Assistant Adapter.

Provides deterministic offline advisory capabilities (parts suggestion,
message drafting, summarization) with explicit provenance and testable
failure modes. Built with a bounded seam ready for Strands integration.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from benchbook.domain.errors import (
    AssistantBusyError,
    AssistantInvalidOutputError,
    AssistantTimeoutError,
    AssistantUnavailableError,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# Pre-computed realistic domain suggestions for typical Tamil Nadu shop repairs
DEVICE_PARTS_KNOWLEDGE: dict[str, list[dict[str, Any]]] = {
    "bldc ceiling fan": [
        {
            "part_name": "BLDC Motor Driver Controller IC (IPM)",
            "part_number": "FD6288Q / EG2133",
            "supplier_name": "Supreme Electronics Spares, Cross Cut Road, Coimbatore",
            "unit_cost_inr": 280.0,
            "availability_status": "in_stock",
            "relevance_reason": "Humming and speed drop typically indicate failed gate driver phase output.",
        },
        {
            "part_name": "SMPS High-Voltage Filter Capacitor (450V 22uF)",
            "part_number": "Rubycon BXW 450V",
            "supplier_name": "Kovai Micro Spares, Gandhipuram",
            "unit_cost_inr": 45.0,
            "availability_status": "in_stock",
            "relevance_reason": "Erratic microcontroller reset caused by dried capacitor ESR ripple.",
        },
    ],
    "split ac inverter pcb": [
        {
            "part_name": "IGBT Inverter Power Module (IPM)",
            "part_number": "STK554U362A / SLLIMM",
            "supplier_name": "Royal Tech Chip Level Hub, Richie Street, Chennai",
            "unit_cost_inr": 1650.0,
            "availability_status": "in_stock",
            "relevance_reason": "E6 error and dead compressor output trace to shorted IPM lower bridge.",
        },
        {
            "part_name": "Current Sense Shunt Resistor (0.02 Ohm 3W)",
            "part_number": "WSL3637",
            "supplier_name": "Supreme Electronics Spares, Cross Cut Road, Coimbatore",
            "unit_cost_inr": 85.0,
            "availability_status": "in_stock",
            "relevance_reason": "Blown alongside IPM during high-voltage surge.",
        },
    ],
    "mixer grinder": [
        {
            "part_name": "Heavy Duty Armature Core (750W Copper)",
            "part_number": "PZ-750-ARM",
            "supplier_name": "Annamalai Electricals & Winding Spares, 100 Feet Road",
            "unit_cost_inr": 550.0,
            "availability_status": "in_stock",
            "relevance_reason": "Commutator segment pitting and high sparking under load.",
        },
        {
            "part_name": "High-Grade Carbon Brush Pair (Grade L)",
            "part_number": "CB-125-P",
            "supplier_name": "Annamalai Electricals & Winding Spares, 100 Feet Road",
            "unit_cost_inr": 60.0,
            "availability_status": "in_stock",
            "relevance_reason": "Worn carbon brushes causing uneven commutator contact.",
        },
        {
            "part_name": "Overload Protector Switch (2.7A Auto-Reset)",
            "part_number": "OLP-2.7A",
            "supplier_name": "Kovai Micro Spares, Gandhipuram",
            "unit_cost_inr": 75.0,
            "availability_status": "in_stock",
            "relevance_reason": "Weak bimetallic strip tripping prematurely.",
        },
    ],
    "microwave oven": [
        {
            "part_name": "High Voltage Magnetron Tube (2M214)",
            "part_number": "2M214-39F",
            "supplier_name": "Supreme Electronics Spares, Cross Cut Road, Coimbatore",
            "unit_cost_inr": 1850.0,
            "availability_status": "in_stock",
            "relevance_reason": "Turntable operates but no RF heating power generated.",
        },
        {
            "part_name": "High Voltage Rectifier Diode (CL01-12)",
            "part_number": "CL01-12 / HVM12",
            "supplier_name": "Kovai Micro Spares, Gandhipuram",
            "unit_cost_inr": 90.0,
            "availability_status": "in_stock",
            "relevance_reason": "Shorted diode pulls down HV transformer secondary.",
        },
    ],
    "laptop": [
        {
            "part_name": "USB Type-C Power Delivery Jack (16-pin SMD)",
            "part_number": "TC-SMD-16P",
            "supplier_name": "Royal Tech Chip Level Hub, Richie Street, Chennai",
            "unit_cost_inr": 180.0,
            "availability_status": "in_stock",
            "relevance_reason": "Damaged CC1/VBUS pins causing intermittent charging and spark damage.",
        },
        {
            "part_name": "Right LCD Hinge Assembly with Brass Standoffs",
            "part_number": "HNG-TP-E14-R",
            "supplier_name": "Royal Tech Chip Level Hub, Richie Street, Chennai",
            "unit_cost_inr": 420.0,
            "availability_status": "in_stock",
            "relevance_reason": "Seized hinge cracked palmrest mounting screw boss.",
        },
    ],
    "smartphone": [
        {
            "part_name": "AMOLED Display Assembly with Frame",
            "part_number": "RN12P-OLED-FRM",
            "supplier_name": "Royal Tech Chip Level Hub, Richie Street, Chennai",
            "unit_cost_inr": 2850.0,
            "availability_status": "in_stock",
            "relevance_reason": "Cracked internal matrix and touch digitizer failure.",
        },
        {
            "part_name": "Type-C Sub-Board Charging PCB Module",
            "part_number": "SUB-RN12P-67W",
            "supplier_name": "Kovai Micro Spares, Gandhipuram",
            "unit_cost_inr": 350.0,
            "availability_status": "in_stock",
            "relevance_reason": "Damaged charging port and microphone circuit.",
        },
    ],
}


class DeterministicAssistantAdapter:
    """Offline deterministic assistant adapter for Benchbook."""

    def __init__(self, mode: str = "deterministic") -> None:
        self.mode = mode

    def _check_failure_mode(self) -> None:
        if self.mode == "timeout":
            raise AssistantTimeoutError("Assistant inference exceeded 10.0s deadline.")
        if self.mode == "busy":
            raise AssistantBusyError("Assistant queue capacity reached (429 concurrency limit).")
        if self.mode == "unavailable":
            raise AssistantUnavailableError("Assistant service is unreachable or offline.")
        if self.mode == "invalid_output":
            raise AssistantInvalidOutputError(
                "Assistant produced ungrounded or unparseable JSON payload."
            )

    def _get_provenance(self) -> dict[str, Any]:
        return {
            "engine": "benchbook_offline_adapter",
            "model": "rule-heuristic-v1",
            "generated_at": _now_iso(),
            "advisory_only": True,
            "requires_human_verification": True,
        }

    def suggest_parts(
        self, device_kind: str, symptoms: str, findings: str | None = None
    ) -> dict[str, Any]:
        """Suggest parts based on device category and reported symptoms."""
        self._check_failure_mode()

        kind_normalized = device_kind.lower().strip()
        suggestions: list[dict[str, Any]] = []

        for key, parts in DEVICE_PARTS_KNOWLEDGE.items():
            if key in kind_normalized or kind_normalized in key:
                suggestions = parts
                break

        if not suggestions:
            # Fallback generic electronics parts
            suggestions = [
                {
                    "part_name": "Standard Power IC & Filter Capacitor Kit",
                    "part_number": "GEN-PWR-KIT",
                    "supplier_name": "Supreme Electronics Spares, Cross Cut Road, Coimbatore",
                    "unit_cost_inr": 350.0,
                    "availability_status": "in_stock",
                    "relevance_reason": f"Generic power supply remediation based on symptom: {symptoms[:60]}",
                }
            ]

        return {
            "device_kind": device_kind,
            "symptoms_analyzed": symptoms,
            "suggestions": suggestions,
            "confidence_score": 0.92 if suggestions else 0.65,
            "provenance": self._get_provenance(),
        }

    def draft_estimate_message(
        self,
        customer_name: str,
        device_kind: str,
        brand_model: str,
        labor_charge_inr: float,
        parts_total_inr: float,
        tax_inr: float,
        total_amount_inr: float,
        promised_date: str | None,
        shop_name: str = "Kovai Tech Bench",
    ) -> dict[str, Any]:
        """Draft a WhatsApp/SMS estimate explanation for customer approval."""
        self._check_failure_mode()

        date_str = promised_date or "within 2-3 business days"
        message_text = (
            f"Vanakkam {customer_name}, greetings from {shop_name}.\n"
            f"We have inspected your {brand_model} ({device_kind}).\n\n"
            f"Cost Estimate:\n"
            f"- Spare Parts: ₹{parts_total_inr:,.2f}\n"
            f"- Bench Service & Labor: ₹{labor_charge_inr:,.2f}\n"
            f"- GST (18%): ₹{tax_inr:,.2f}\n"
            f"Total Payable: ₹{total_amount_inr:,.2f}\n"
            f"Estimated Ready Date: {date_str}\n\n"
            f"Please reply 'APPROVE' to authorize this repair or call us if you have any questions.\n"
            f"(Note: We will not order parts or start work until you confirm.)"
        )

        return {
            "channel": "whatsapp",
            "message_text": message_text,
            "character_count": len(message_text),
            "provenance": self._get_provenance(),
        }

    def draft_pickup_notification(
        self,
        customer_name: str,
        device_kind: str,
        brand_model: str,
        total_amount_inr: float,
        warranty_days: int = 30,
        shop_name: str = "Kovai Tech Bench",
        shop_address: str = "Gandhipuram, Coimbatore",
    ) -> dict[str, Any]:
        """Draft a pickup notification when repair and quality checks are completed."""
        self._check_failure_mode()

        message_text = (
            f"Vanakkam {customer_name}, your {brand_model} ({device_kind}) has successfully passed "
            f"all bench quality and burn-in tests!\n\n"
            f"It is ready for pickup at {shop_name}, {shop_address}.\n"
            f"Total Amount Due: ₹{total_amount_inr:,.2f}\n"
            f"Service Warranty: {warranty_days} days included.\n"
            f"Payment Modes: UPI (GPay/PhonePe), Cash, or Debit/Credit Card.\n\n"
            f"Store Hours: 9:30 AM to 8:30 PM (Mon-Sat). Thank you for choosing {shop_name}!"
        )

        return {
            "channel": "whatsapp",
            "message_text": message_text,
            "character_count": len(message_text),
            "provenance": self._get_provenance(),
        }
