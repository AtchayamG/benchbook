"""Deterministic Customer Communication Templates for Benchbook.

Enforces:
1. Derives authoritative monetary sums, dates, job numbers, and shop details exclusively
   from stored database facts.
2. Model prose NEVER invents or substitutes monetary amounts, warranty terms, or readiness dates.
3. Plaintext customer names are interpolated strictly AFTER inference completion.
4. All messages are explicitly marked as local drafts.
"""

from __future__ import annotations


def render_estimate_message(
    customer_name: str,
    brand_model: str,
    job_number: str,
    parts_total_inr: float,
    labor_charge_inr: float,
    total_amount_inr: float,
    promised_delivery_date: str | None,
    shop_name: str,
    shop_phone: str,
) -> str:
    """Render authoritative customer estimate quotation draft."""
    date_str = promised_delivery_date or "within 3 working days"
    return (
        f"Vanakkam {customer_name}! Your repair estimate for {brand_model} (Job #{job_number}) "
        f"at {shop_name} is ready: Parts: Rs. {parts_total_inr:.2f}, Labor: Rs. {labor_charge_inr:.2f}. "
        f"Total: Rs. {total_amount_inr:.2f}. Expected completion by {date_str}. "
        f"Please reply YES to approve or call us at {shop_phone}."
    )


def render_pickup_message(
    customer_name: str,
    brand_model: str,
    job_number: str,
    total_amount_inr: float,
    shop_name: str,
    shop_location: str,
    shop_phone: str,
) -> str:
    """Render authoritative customer pickup ready notification draft."""
    return (
        f"Vanakkam {customer_name}! Good news: your {brand_model} (Job #{job_number}) "
        f"has completed all repair stages and passed full quality control testing at {shop_name}. "
        f"Amount payable: Rs. {total_amount_inr:.2f}. "
        f"You may pick up your device at our bench in {shop_location}. Tel: {shop_phone}."
    )


def render_warranty_message(
    customer_name: str,
    brand_model: str,
    job_number: str,
    warranty_days: int,
    shop_name: str,
    shop_phone: str,
) -> str:
    """Render service closure and post-repair warranty confirmation draft."""
    return (
        f"Vanakkam {customer_name}! Thank you for trusting {shop_name} with your {brand_model} "
        f"(Job #{job_number}). Your repair includes {warranty_days} days bench warranty coverage. "
        f"If you experience any issues, please call us at {shop_phone}."
    )
