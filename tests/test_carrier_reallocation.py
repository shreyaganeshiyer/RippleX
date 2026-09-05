import unittest

from backend.disruption_parser import DisruptionEvent
from backend.entity_resolver import resolve_disruption
from backend.impact_engine import assess_impact
from backend.response_engine import generate_response_options


class CarrierReallocationRegressionTests(unittest.TestCase):
    def test_sh003_does_not_offer_bangalore_or_mumbai_as_sources(self):
        """Open local demand prevents a source transfer commitment."""
        event = DisruptionEvent(
            event_type="carrier_delay",
            supplier_name=None,
            carrier_name="BlueDart",
            location="Chennai Distribution",
            affected_products=["Y-100"],
            affected_shipments=["SH003"],
            delay_days=10,
            summary="Carrier delay for SH003.",
            confidence=1.0,
        )

        impact = assess_impact(resolve_disruption(event))
        options = generate_response_options(impact)
        reallocations = [
            option
            for option in options
            if option.option_type == "REALLOCATE"
        ]

        self.assertEqual(reallocations, [])
        self.assertFalse(any(
            "Bangalore Central" in option.title
            or "Mumbai Distribution" in option.title
            for option in options
        ))


if __name__ == "__main__":
    unittest.main()
