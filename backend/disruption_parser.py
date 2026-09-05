import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field, field_validator


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set."
    )

client = genai.Client(api_key=api_key)


# ============================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================


class DisruptionEvent(BaseModel):
    """
    Facts extracted from an unstructured disruption notice.

    This model represents what the notice says.
    It does not represent calculated business impact.
    """

    event_type: str = Field(
        description=(
            "Type of disruption, such as "
            "supplier_production_halt, carrier_delay, "
            "warehouse_incident, shipment_delay, or other."
        )
    )

    supplier_name: Optional[str] = Field(
    default=None,
    description="Supplier/company name ONLY, without city or geographic location. "
                "For example, 'ABC Components Bangalore' means supplier_name='ABC Components'."
        )

    carrier_name: Optional[str] = Field(
        default=None,
        description=(
            "Carrier company explicitly mentioned in the notice. "
            "This is informational metadata and is not a database entity."
        ),
    )

    location: Optional[str] = Field(
    default=None,
    description="Geographic location/city mentioned separately from the supplier name."
    )

    warehouse_name: Optional[str] = Field(
        default=None,
        description=(
            "Warehouse name explicitly mentioned in the notice. "
            "Extract it only when the notice clearly identifies "
            "a warehouse or distribution center."
        ),
    )

    affected_products: list[str] = Field(
        default_factory=list,
        description=(
            "Only product names or product identifiers explicitly "
            "affected by the disruption. Do not include shipment IDs, "
            "order IDs, warehouse IDs, supplier IDs, or descriptive "
            "words such as 'components', 'products', or 'items'. "
            "For example, extract 'Y-100' rather than "
            "'Y-100 components'."
        ),
    )

    affected_shipments: list[str] = Field(
        default_factory=list,
        description=(
            "Shipment IDs explicitly mentioned in the notice, such "
            "as SH001 or SH002. These must never be placed in "
            "affected_products."
        ),
    )

    delay_days: Optional[int] = Field(
        default=None,
        description=(
            "Expected delay in days when explicitly stated or "
            "clearly stated as an approximate duration."
        ),
    )

    summary: str = Field(
        description=(
            "Short factual summary of the disruption without "
            "adding information that is not present in the notice."
        ),
    )

    confidence: float = Field(
        description=(
            "Confidence from 0 to 1 in the extraction. "
            "Lower confidence when the notice is ambiguous."
        ),
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(
        cls,
        value: float,
    ) -> float:
        return max(0.0, min(1.0, value))


# ============================================================
# PARSER
# ============================================================


def parse_disruption(
    notice: str,
) -> DisruptionEvent:
    """
    Extract structured disruption facts from an unstructured notice.

    Gemini is used only for language understanding.

    It does NOT:
        - calculate business impact
        - inspect the database
        - identify affected orders
        - calculate shortages
        - recommend actions
        - invent entities
    """

    cleaned_notice = notice.strip()

    if not cleaned_notice:
        raise ValueError(
            "Disruption notice cannot be empty."
        )

    prompt = f"""
You are the structured extraction component of RippleX,
an AI supply-chain disruption response system.

Your ONLY task is to extract factual information explicitly
contained in the disruption notice.

IMPORTANT ENTITY RULES:

1. SUPPLIERS
   Extract the supplier company name exactly as it appears
   in the notice.

2. PRODUCTS
   Extract ONLY actual product names or product identifiers.

   If the notice says:
       "Y-100 components"
   extract:
       "Y-100"

   If the notice says:
       "X-200 products"
   extract:
       "X-200"

   Remove generic descriptive suffixes such as:
       components
       products
       product
       items
       units
       parts

   Do NOT invent or transform the actual product identifier.

2A. CARRIERS
   Extract a carrier company name only when it is explicitly stated.
   carrier_name is informational metadata. Do not map it to a supplier.

3. SHIPMENTS
   Shipment identifiers look like:
       SH001
       SH002
       SH123

   Put shipment identifiers ONLY in affected_shipments.

   NEVER put shipment IDs inside affected_products.

4. ORDERS
   Order identifiers look like:
       ORD001
       ORD101

   Do not put order IDs in affected_products or
   affected_shipments.

5. WAREHOUSES
   If the notice explicitly identifies a warehouse, distribution
   center, fulfillment center, or warehouse facility, extract its
   name into warehouse_name.

   Examples:

       "Chennai Distribution warehouse"
       → warehouse_name = "Chennai Distribution"

       "Mumbai Distribution"
       → warehouse_name = "Mumbai Distribution"

   If a warehouse ID such as WH002 is explicitly mentioned,
   do not put it in affected_products or affected_shipments.

   Do not invent or infer a warehouse name from a city alone.

   A location such as "Chennai" should remain in location unless
   the notice explicitly identifies a warehouse there.

6. SUPPLIER IDS
   Identifiers such as SUP001 are supplier IDs, not products.

7. DO NOT GUESS
   Do not assume that an entity exists in RippleX's database.
   Do not convert an ambiguous phrase into a specific entity.

8. AMBIGUITY
   If the notice says something broad such as:
       "X-series"
   preserve it as written rather than guessing which
   specific product it means.

9. BUSINESS IMPACT
   Do NOT calculate:
       - affected orders
       - inventory shortages
       - units at risk
       - order value at risk
       - response options
       - recommendations

10. SHIPMENT DISCOVERY
    If the notice mentions a supplier and product but does not
    explicitly mention shipment IDs, leave affected_shipments
    empty.

    RippleX's deterministic backend will discover affected
    shipments from its own database.

11. SUMMARY
    The summary must contain only facts stated in the notice.

12. CONFIDENCE
    Return a value between 0 and 1 representing confidence
    in the extraction itself.

13.SUPPLIER NAME AND LOCATION:
- supplier_name must contain ONLY the supplier/company name as it appears in the database.
- location must contain the geographic location separately.
- Do NOT include the city/location as part of supplier_name.
- Example:
  "ABC Components Bangalore" → supplier_name = "ABC Components", location = "Bangalore"
  "Global Parts Chennai" → supplier_name = "Global Parts", location = "Chennai"
  "Nova Supplies Pune" → supplier_name = "Nova Supplies", location = "Pune"
  "Prime Manufacturing Mumbai" → supplier_name = "Prime Manufacturing", location = "Mumbai"
  "Vertex Industries Delhi" → supplier_name = "Vertex Industries", location = "Delhi"

DISRUPTION NOTICE:
{cleaned_notice}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": DisruptionEvent,
        },
    )

    if not response.text:
        raise ValueError(
            "Gemini returned an empty extraction response."
        )

    return DisruptionEvent.model_validate_json(
        response.text
    )
