from dataclasses import dataclass
from typing import Any

from backend.impact_engine import ImpactAssessment


# ============================================================
# RESPONSE OPTION MODEL
# ============================================================

@dataclass(frozen=True)
class ResponseOption:
    option_type: str
    title: str
    description: str
    units_recovered: int
    orders_helped: int
    estimated_cost: float
    tradeoff: str
    feasible: bool
    reason: str
    evidence: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_type": self.option_type,
            "title": self.title,
            "description": self.description,
            "units_recovered": self.units_recovered,
            "orders_helped": self.orders_helped,
            "estimated_cost": self.estimated_cost,
            "tradeoff": self.tradeoff,
            "feasible": self.feasible,
            "reason": self.reason,
            "evidence": [
                evidence.to_dict()
                if hasattr(evidence, "to_dict")
                else evidence
                for evidence in self.evidence
            ],
        }


# ============================================================
# HELPERS
# ============================================================

def _calculate_order_units_at_risk(
    impact: ImpactAssessment,
) -> int:
    return sum(
        order.shortage_quantity
        for order in impact.affected_orders
        if order.shortage_quantity > 0
    )


def _count_orders_helped_by_supply(
    affected_orders,
    product_id: str,
    warehouse_id: str,
    units_available: int,
) -> int:
    """
    Determine how many affected orders at the destination can
    actually be covered by the recovered units.

    Orders are considered in urgency order.
    """

    if units_available <= 0:
        return 0

    orders = [
        order
        for order in affected_orders
        if (
            order.product_id == product_id
            and order.warehouse_id == warehouse_id
            and order.shortage_quantity > 0
        )
    ]

    orders.sort(
        key=lambda order: (
            -order.urgency_score,
            order.promised_date or "9999-12-31",
            -order.order_value_at_risk,
            order.order_id,
        )
    )

    remaining = units_available
    helped = 0

    for order in orders:
        if remaining <= 0:
            break

        covered = min(
            remaining,
            order.shortage_quantity,
        )

        if covered > 0:
            helped += 1
            remaining -= covered

    return helped


def _make_evidence(
    source_type: str,
    source_id: str,
    description: str,
):
    """
    Reuse the Evidence model from impact_engine without
    duplicating its implementation.
    """

    from backend.impact_engine import Evidence

    return Evidence(
        source_type=source_type,
        source_id=source_id,
        description=description,
    )


# ============================================================
# REALLOCATION
# ============================================================

def _find_reallocation_opportunities(
    impact: ImpactAssessment,
) -> list[ResponseOption]:

    opportunities: list[ResponseOption] = []

    # --------------------------------------------------------
    # 1. Find shortages by PRODUCT + DESTINATION WAREHOUSE
    # --------------------------------------------------------

    shortage_by_product_warehouse: dict[
        tuple[str, str],
        int,
    ] = {}

    for order in impact.affected_orders:

        if order.shortage_quantity <= 0:
            continue

        key = (
            order.product_id,
            order.warehouse_id,
        )

        shortage_by_product_warehouse[key] = (
            shortage_by_product_warehouse.get(key, 0)
            + order.shortage_quantity
        )

    if not shortage_by_product_warehouse:
        return opportunities

    # --------------------------------------------------------
    # 2. Group inventory by product
    # --------------------------------------------------------

    inventory_by_product: dict[str, list] = {}

    for inventory in impact.inventory_impacts:

        inventory_by_product.setdefault(
            inventory.product_id,
            [],
        ).append(inventory)

    # --------------------------------------------------------
    # 3. Find genuine surplus warehouses
    # --------------------------------------------------------

    for product_id, inventories in inventory_by_product.items():

        destinations = {
            warehouse_id: shortage
            for (
                pid,
                warehouse_id,
            ), shortage in shortage_by_product_warehouse.items()
            if (
                pid == product_id
                and shortage > 0
            )
        }

        if not destinations:
            continue

        sources = []

        for inventory in inventories:

            # A shortage warehouse cannot simultaneously be
            # treated as a source.
            if inventory.warehouse_id in destinations:
                continue

            if inventory.available_quantity <= 0:
                continue

            warehouse_demand = sum(
                order.quantity
                for order in impact.affected_orders
                if (
                    order.product_id == product_id
                    and order.warehouse_id == inventory.warehouse_id
                )
            )

            surplus = max(
                inventory.available_quantity
                - warehouse_demand,
                0,
            )

            if surplus > 0:
                sources.append(
                    (
                        inventory,
                        surplus,
                    )
                )

        if not sources:
            continue

        # ----------------------------------------------------
        # 4. Allocate source surplus to affected destinations
        # ----------------------------------------------------

        remaining_shortage = dict(destinations)

        for source, source_surplus in sources:

            remaining_source_stock = source_surplus

            for destination_id in list(
                remaining_shortage.keys()
            ):

                if remaining_source_stock <= 0:
                    break

                destination_shortage = (
                    remaining_shortage[destination_id]
                )

                if destination_shortage <= 0:
                    continue

                units_to_move = min(
                    remaining_source_stock,
                    destination_shortage,
                )

                if units_to_move <= 0:
                    continue

                orders_helped = _count_orders_helped_by_supply(
                    impact.affected_orders,
                    product_id,
                    destination_id,
                    units_to_move,
                )

                estimated_cost = units_to_move * 15

                evidence = (
                    _make_evidence(
                        source_type="inventory",
                        source_id=(
                            f"{source.warehouse_id}:{product_id}"
                        ),
                        description=(
                            f"{source.warehouse_name} has "
                            f"{source.available_quantity} available "
                            f"units of {source.product_name}."
                        ),
                    ),
                    _make_evidence(
                        source_type="calculation",
                        source_id=(
                            f"reallocation:"
                            f"{source.warehouse_id}:"
                            f"{destination_id}:"
                            f"{product_id}"
                        ),
                        description=(
                            f"{source.warehouse_name} has "
                            f"{source_surplus} units of surplus "
                            f"{source.product_name} after accounting "
                            f"for its pending demand. "
                            f"{destination_id} has "
                            f"{destination_shortage} units of "
                            f"shortage."
                        ),
                    ),
                )

                opportunities.append(
                    ResponseOption(
                        option_type="REALLOCATE",

                        title=(
                            f"Reallocate "
                            f"{units_to_move} units of "
                            f"{source.product_name}"
                        ),

                        description=(
                            f"Move {units_to_move} units of "
                            f"{source.product_name} from "
                            f"{source.warehouse_name} to "
                            f"the warehouse serving affected "
                            f"customer orders."
                        ),

                        units_recovered=units_to_move,

                        orders_helped=orders_helped,

                        estimated_cost=estimated_cost,

                        tradeoff=(
                            f"Uses existing surplus inventory at "
                            f"{source.warehouse_name}, avoiding "
                            f"dependence on the disrupted shipment. "
                            f"Trade-off: ₹{estimated_cost:,.0f} "
                            f"transfer cost and a smaller inventory "
                            f"buffer at the source warehouse."
                        ),

                        feasible=True,

                        reason=(
                            f"{source.warehouse_name} has "
                            f"{source.available_quantity} available "
                            f"units, with approximately "
                            f"{source_surplus} units of surplus "
                            f"after its pending demand. "
                            f"{destination_id} has "
                            f"{destination_shortage} units "
                            f"of demand at risk."
                        ),

                        evidence=evidence,
                    )
                )

                remaining_source_stock -= units_to_move
                remaining_shortage[destination_id] -= units_to_move

    return opportunities


# ============================================================
# MAIN RESPONSE ENGINE
# ============================================================

def generate_response_options(
    impact: ImpactAssessment,
) -> list[ResponseOption]:

    # No business impact = no response actions.
    if not impact.has_impact:
        return []

    affected_orders = list(
        impact.affected_orders
    )

    total_units_at_risk = (
        _calculate_order_units_at_risk(impact)
    )

    options: list[ResponseOption] = []

    # ========================================================
    # OPTION 1 — EXPEDITE
    # ========================================================

    expedited_shipments = [
        shipment
        for shipment in impact.affected_shipments
        if shipment.quantity > 0
    ]

    expedite_units = sum(
        shipment.quantity
        for shipment in expedited_shipments
    )

    expedite_units_recovered = min(
        expedite_units,
        total_units_at_risk,
    )

    # --------------------------------------------------------
    # Determine which orders the recovered supply can cover.
    #
    # Shipment supply is mapped to the product + destination
    # warehouse instead of blindly claiming that every affected
    # order benefits.
    # --------------------------------------------------------

    remaining_recovery = expedite_units_recovered
    orders_helped_by_expedite = 0

    for shipment in expedited_shipments:

        if remaining_recovery <= 0:
            break

        shipment_orders = [
            order
            for order in affected_orders
            if (
                order.product_id == shipment.product_id
                and order.warehouse_id == shipment.warehouse_id
                and order.shortage_quantity > 0
            )
        ]

        shipment_orders.sort(
            key=lambda order: (
                -order.urgency_score,
                order.promised_date or "9999-12-31",
                -order.order_value_at_risk,
                order.order_id,
            )
        )

        shipment_recovery = min(
            shipment.quantity,
            remaining_recovery,
        )

        for order in shipment_orders:

            if shipment_recovery <= 0:
                break

            covered = min(
                shipment_recovery,
                order.shortage_quantity,
            )

            if covered > 0:
                orders_helped_by_expedite += 1
                shipment_recovery -= covered
                remaining_recovery -= covered

    # Demo assumption:
    # ₹25 per expedited unit.
    expedite_cost = (
        expedite_units_recovered * 25
    )

    expedite_evidence = tuple(
        _make_evidence(
            source_type="shipment",
            source_id=shipment.shipment_id,
            description=(
                f"{shipment.shipment_id} contains "
                f"{shipment.quantity} units of "
                f"{shipment.product_name} destined for "
                f"{shipment.warehouse_name}."
            ),
        )
        for shipment in expedited_shipments
    )

    options.append(
        ResponseOption(
            option_type="EXPEDITE",

            title="Expedite disrupted shipment",

            description=(
                "Pay for expedited transport or supplier "
                "recovery to restore disrupted incoming supply."
            ),

            units_recovered=(
                expedite_units_recovered
            ),

            orders_helped=(
                orders_helped_by_expedite
            ),

            estimated_cost=(
                expedite_cost
            ),

            tradeoff=(
                "Higher logistics cost, but preserves "
                "customer orders without consuming "
                "inventory from another warehouse."
            ),

            feasible=(
                expedite_units_recovered > 0
                and orders_helped_by_expedite > 0
            ),

            reason=(
                "Affected incoming shipment quantity is "
                "available for expedited recovery and can "
                "be mapped to affected orders."
            ),

            evidence=expedite_evidence,
        )
    )

    # ========================================================
    # OPTION 2 — PART SHIP
    # ========================================================

    part_ship_units = sum(
        order.quantity - order.shortage_quantity
        for order in affected_orders
        if (
            order.quantity
            > order.shortage_quantity
        )
    )

    part_ship_orders = sum(
        1
        for order in affected_orders
        if (
            0 < order.shortage_quantity
            < order.quantity
        )
    )

    part_ship_evidence = tuple(
        _make_evidence(
            source_type="order",
            source_id=order.order_id,
            description=(
                f"{order.order_id} can receive "
                f"{order.quantity - order.shortage_quantity} "
                f"units immediately, with "
                f"{order.shortage_quantity} units exposed."
            ),
        )
        for order in affected_orders
        if (
            0 < order.shortage_quantity
            < order.quantity
        )
    )

    options.append(
        ResponseOption(
            option_type="PART_SHIP",

            title="Part-ship affected orders",

            description=(
                "Ship available units now and deliver "
                "the remaining quantity later."
            ),

            units_recovered=(
                part_ship_units
            ),

            orders_helped=(
                part_ship_orders
            ),

            estimated_cost=0.0,

            tradeoff=(
                "Customers receive partial fulfillment "
                "sooner, but remaining units still "
                "require follow-up."
            ),

            feasible=(
                part_ship_orders > 0
            ),

            reason=(
                "At least one affected order can be "
                "partially fulfilled using currently "
                "available inventory."
            ),

            evidence=part_ship_evidence,
        )
    )

    # ========================================================
    # OPTION 3 — CUSTOMER NOTIFICATION
    # ========================================================

    notification_evidence = tuple(
        _make_evidence(
            source_type="order",
            source_id=order.order_id,
            description=(
                f"{order.order_id} for {order.customer_name} "
                f"is currently affected by the disruption."
            ),
        )
        for order in affected_orders
    )

    options.append(
        ResponseOption(
            option_type="CUSTOMER_NOTIFY",

            title="Notify affected customers",

            description=(
                "Communicate expected delays and "
                "revised fulfillment expectations."
            ),

            units_recovered=0,

            orders_helped=len(
                affected_orders
            ),

            estimated_cost=0.0,

            tradeoff=(
                "Does not recover inventory, but reduces "
                "surprise and gives customers time "
                "to adjust."
            ),

            feasible=(
                len(affected_orders) > 0
            ),

            reason=(
                "Affected customer orders "
                "have been identified."
            ),

            evidence=notification_evidence,
        )
    )

    # ========================================================
    # OPTION 4 — REALLOCATION
    # ========================================================

    options.extend(
        _find_reallocation_opportunities(
            impact
        )
    )

    return options


# ============================================================
# CLI OUTPUT
# ============================================================

def print_response_options(
    options: list[ResponseOption],
) -> None:

    print()
    print("=" * 60)
    print("RippleX Response Options")
    print("=" * 60)

    if not options:
        print("No response options available.")
        return

    for index, option in enumerate(
        options,
        start=1,
    ):

        print()
        print(
            f"{index}. {option.title}"
        )

        print(
            f"   Type: "
            f"{option.option_type}"
        )

        print(
            f"   Units recovered: "
            f"{option.units_recovered}"
        )

        print(
            f"   Orders helped: "
            f"{option.orders_helped}"
        )

        print(
            f"   Estimated cost: "
            f"₹{option.estimated_cost:,.2f}"
        )

        print(
            f"   Feasible: "
            f"{option.feasible}"
        )

        print(
            f"   Trade-off: "
            f"{option.tradeoff}"
        )

        print(
            f"   Reason: "
            f"{option.reason}"
        )


# ============================================================
# DETERMINISTIC TEST
# ============================================================

if __name__ == "__main__":

    from types import SimpleNamespace

    # This test does NOT call Gemini.

    impact = SimpleNamespace(

        has_impact=True,

        affected_shipments=[
            SimpleNamespace(
                shipment_id="SH001",
                quantity=120,
                product_id="P001",
                product_name="X-200",
                warehouse_id="WH001",
                warehouse_name="Bangalore Central",
            )
        ],

        affected_orders=[

            SimpleNamespace(
                order_id="ORD101",
                customer_name="Reliance Retail",
                product_id="P001",
                product_name="X-200",
                quantity=40,
                warehouse_id="WH001",
                warehouse_name="Bangalore Central",
                shortage_quantity=40,
                urgency_score=90,
                promised_date="2026-09-08",
                order_value_at_risk=34000,
            ),

            SimpleNamespace(
                order_id="ORD102",
                customer_name="TechWorld Distribution",
                product_id="P001",
                product_name="X-200",
                quantity=30,
                warehouse_id="WH001",
                warehouse_name="Bangalore Central",
                shortage_quantity=30,
                urgency_score=85,
                promised_date="2026-09-10",
                order_value_at_risk=25500,
            ),

        ],

        inventory_impacts=[

            SimpleNamespace(
                product_id="P001",
                product_name="X-200",
                warehouse_id="WH001",
                warehouse_name="Bangalore Central",
                available_quantity=25,
            ),

            SimpleNamespace(
                product_id="P001",
                product_name="X-200",
                warehouse_id="WH002",
                warehouse_name="Chennai Distribution",
                available_quantity=110,
            ),

        ],
    )

    options = generate_response_options(
        impact
    )

    print_response_options(
        options
    )