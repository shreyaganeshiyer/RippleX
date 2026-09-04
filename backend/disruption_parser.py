import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set."
    )

client = genai.Client(api_key=api_key)


# ---------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------

class DisruptionEvent(BaseModel):
    event_type: str = Field(
        description=(
            "Type of disruption, such as supplier_production_halt, "
            "carrier_delay, warehouse_incident, or other."
        )
    )

    supplier_name: Optional[str] = Field(
        default=None,
        description="Supplier mentioned in the notice, if any."
    )

    location: Optional[str] = Field(
        default=None,
        description="Location mentioned in the notice, if any."
    )

    affected_products: list[str] = Field(
        default_factory=list,
        description=(
            "Product names or product identifiers explicitly "
            "mentioned in the notice."
        )
    )

    delay_days: Optional[int] = Field(
        default=None,
        description=(
            "Expected delay in days if explicitly stated or "
            "clearly inferable from the notice."
        )
    )

    summary: str = Field(
        description="Short factual summary of what happened."
    )

    confidence: float = Field(
        description=(
            "Confidence from 0 to 1 in the extracted information."
        )
    )


# ---------------------------------------------------------
# Parser
# ---------------------------------------------------------

def parse_disruption(notice: str) -> DisruptionEvent:

    prompt = f"""
You are the disruption extraction component of RippleX,
a supply-chain disruption response system.

Your job is ONLY to extract facts from the disruption notice.

Do NOT:
- calculate business impact
- identify affected orders
- calculate inventory shortages
- recommend actions
- invent missing information
- assume a supplier or product exists in our database

If something is not present in the notice, return null
for optional fields or an empty list where appropriate.

If the notice is ambiguous, preserve the ambiguity rather
than guessing.

Extract:
- disruption type
- supplier
- location
- affected products
- expected delay
- factual summary
- confidence

DISRUPTION NOTICE:
{notice}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": DisruptionEvent,
        },
    )

    return DisruptionEvent.model_validate_json(response.text)


# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

if __name__ == "__main__":

    notice = """
    Hi team,

    Due to an unexpected production issue at our Bangalore
    facility, we won't be able to dispatch the X-200 and X-300
    orders scheduled this week.

    We expect operations to resume in around 10 days.

    Regards,
    ABC Components
    """

    result = parse_disruption(notice)

    print("\nRippleX Disruption Parser")
    print("=" * 40)

    print(result.model_dump_json(indent=2))