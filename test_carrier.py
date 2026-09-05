from backend.disruption_parser import DisruptionEvent
from backend.entity_resolver import resolve_disruption
from backend.impact_engine import assess_impact


def run_test(name, event):
    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    resolved = resolve_disruption(event)

    print("\nResolution:")
    print("  Supplier:", resolved.supplier.entity_name if resolved.supplier else None)
    print("  Products:", [
        (p.product_id, p.product_name)
        for p in resolved.products
    ])
    print(
    "  Affected shipment IDs:",
    event.affected_shipments
    )   
    print("  Warehouse:", resolved.warehouse.entity_name if resolved.warehouse else None)
    print("  Human review:", resolved.requires_human_review)

    impact = assess_impact(resolved)

    print("\nImpact:")
    print("  Has impact:", impact.has_impact)
    print("  Summary:", impact.summary)
    print("  Orders at risk:", impact.total_orders_at_risk)
    print("  Units at risk:", impact.total_units_at_risk)

    return resolved, impact


# ============================================================
# TEST 1 — REAL CARRIER DELAY: SH003
# ============================================================

event_1 = DisruptionEvent(
    event_type="carrier_delay",
    supplier_name=None,
    location="Chennai",
    affected_products=["Y-100"],
    affected_shipments=["SH003"],
    delay_days=10,
    summary="BlueDart reports a 10 day delay affecting shipment SH003.",
    confidence=1.0,
)

run_test(
    "TEST 1 — SH003 carrier delay",
    event_1,
)


# ============================================================
# TEST 2 — NONEXISTENT SHIPMENT
# ============================================================

event_2 = DisruptionEvent(
    event_type="carrier_delay",
    supplier_name=None,
    location="Chennai",
    affected_products=[],
    affected_shipments=["SH999"],
    delay_days=10,
    summary="Carrier reports a delay affecting shipment SH999.",
    confidence=1.0,
)

run_test(
    "TEST 2 — Nonexistent shipment SH999",
    event_2,
)


# ============================================================
# TEST 3 — CARRIER NOTICE WITHOUT SHIPMENT ID
# ============================================================

event_3 = DisruptionEvent(
    event_type="carrier_delay",
    supplier_name=None,
    location="Chennai",
    affected_products=["Y-100"],
    affected_shipments=[],
    delay_days=10,
    summary="Carrier reports that Y-100 shipments to Chennai are delayed.",
    confidence=1.0,
)

run_test(
    "TEST 3 — Product/location only",
    event_3,
)


# ============================================================
# DATABASE INVENTORY CHECK
# ============================================================

print("\n" + "=" * 70)
print("DATABASE CHECK — P004 / Y-100")
print("=" * 70)

from backend.database import get_inventory

for row in get_inventory("P004"):
    print(dict(row))