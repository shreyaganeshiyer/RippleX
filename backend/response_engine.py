from dataclasses import dataclass
from typing import Any

from backend.impact_engine import ImpactAssessment, Evidence


# ============================================================
# CONFIGURATION
# ============================================================
#
# These are planning assumptions, not claims about real carrier
# pricing. Keeping them centralized makes them easy to replace
# with real logistics-cost data later.
#

EXPEDITE_COST_PER_UNIT = 25.0
REALLOCATION_COST_PER_UNIT = 15.0


# ============================================================
# RESPONSE OPTION MODEL
# ============================================================


@dataclass(frozen=True)
class ResponseOption:
    """
    A deterministic response option generated from the current
    supply-chain state.

    The response engine does not invent supply-chain facts.
    All quantities and affected entities originate from the
    ImpactAssessment.
    """

    option_type: str
    title: str
    description: str

    units_recovered: int
    orders_helped: int

    estimated_cost: float

    tradeoff: str

    feasible: bool
    reason: str

    evidence: tuple[Evidence, ...] = ()

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
                for evidence in self.evidence
            ],
        }


# ============================================================
# GENERIC HELPERS
# ============================================================


def _make_evidence(
    source_type: str,
    source_id: str,
    description: str,
) -> Evidence:
    """
    Create standardized evidence records.

    Every generated response option should be traceable back
    to either source data or a deterministic calculation.
    """

    return Evidence(
        source_type=source_type,
        source_id=source_id,
        description=description,
    )


def _order_sort_key(order) -> tuple:
    """
    Consistent urgency ordering.

    Higher urgency score comes first.
    Earlier promised dates come first.
    Higher order value is used as a secondary tie-breaker.
    """

    return (
        -order.urgency_score,
        order.promised_date or "9999-12-31",
        -order.order_value_at_risk,
        order.order_id,
    )


def _affected_orders_with_shortage(
    impact: ImpactAssessment,
) -> list:
    """
    Return only orders that currently have an actual shortage.
    """

    return [
        order
        for order in impact.affected_orders
        if order.shortage_quantity > 0
    ]


def _total_units_at_risk(
    impact: ImpactAssessment,
) -> int:
    """
    Calculate total customer units currently exposed.
    """

    return sum(
        max(order.shortage_quantity, 0)
        for order in impact.affected_orders
    )


def _count_orders_helped(
    affected_orders: list,
    product_id: str,
    warehouse_id: str,
    available_units: int,
) -> int:
    """
    Determine how many affected orders can receive at least one
    unit from a given supply recovery.

    Orders are considered in deterministic urgency order.
    """

    if available_units <= 0:
        return 0

    candidate_orders = [
        order
        for order in affected_orders
        if (
            order.product_id == product_id
            and order.warehouse_id == warehouse_id
            and order.shortage_quantity > 0
        )
    ]

    candidate_orders.sort(key=_order_sort_key)

    remaining = available_units
    helped = 0

    for order in candidate_orders:
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


# ============================================================
# EXPEDITE
# ============================================================


def _generate_expedite_option(
    impact: ImpactAssessment,
) -> ResponseOption:
    """
    Generate an expedite option using only affected incoming
    shipments and the orders those shipments can actually serve.

    Shipment supply is mapped by product + destination warehouse.
    """

    affected_orders = _affected_orders_with_shortage(impact)

    if not impact.affected_shipments:
        return ResponseOption(
            option_type="EXPEDITE",
            title="Expedite disrupted shipments",
            description=(
                "Accelerate affected incoming shipments to "
                "restore customer-facing supply."
            ),
            units_recovered=0,
            orders_helped=0,
            estimated_cost=0.0,
            tradeoff=(
                "No affected incoming shipment is available "
                "for expedited recovery."
            ),
            feasible=False,
            reason=(
                "The current disruption assessment does not "
                "contain an affected active shipment."
            ),
            evidence=(),
        )

    total_recoverable_units = 0
    total_orders_helped = 0

    evidence: list[Evidence] = []

    for shipment in impact.affected_shipments:

        if shipment.quantity <= 0:
            continue

        shipment_orders = [
            order
            for order in affected_orders
            if (
                order.product_id == shipment.product_id
                and order.warehouse_id == shipment.warehouse_id
            )
        ]

        if not shipment_orders:
            continue

        shipment_orders.sort(key=_order_sort_key)

        remaining_supply = shipment.quantity
        shipment_recovered = 0
        shipment_orders_helped = 0

        for order in shipment_orders:

            if remaining_supply <= 0:
                break

            if order.shortage_quantity <= 0:
                continue

            covered = min(
                remaining_supply,
                order.shortage_quantity,
            )

            if covered <= 0:
                continue

            shipment_recovered += covered
            shipment_orders_helped += 1
            remaining_supply -= covered

        if shipment_recovered <= 0:
            continue

        total_recoverable_units += shipment_recovered
        total_orders_helped += shipment_orders_helped

        evidence.append(
            _make_evidence(
                source_type="shipment",
                source_id=shipment.shipment_id,
                description=(
                    f"{shipment.shipment_id} contains "
                    f"{shipment.quantity} units of "
                    f"{shipment.product_name} destined for "
                    f"{shipment.warehouse_name}. "
                    f"{shipment_recovered} units can be mapped "
                    f"to currently affected customer demand."
                ),
            )
        )

    if total_recoverable_units <= 0:
        return ResponseOption(
            option_type="EXPEDITE",
            title="Expedite disrupted shipments",
            description=(
                "Accelerate affected incoming shipments to "
                "restore customer-facing supply."
            ),
            units_recovered=0,
            orders_helped=0,
            estimated_cost=0.0,
            tradeoff=(
                "Expediting cannot currently be justified because "
                "the affected shipment quantities cannot be mapped "
                "to a current customer shortage."
            ),
            feasible=False,
            reason=(
                "Affected shipments exist, but their supply cannot "
                "currently be mapped to affected customer orders."
            ),
            evidence=tuple(evidence),
        )

    estimated_cost = (
        total_recoverable_units
        * EXPEDITE_COST_PER_UNIT
    )

    evidence.append(
        _make_evidence(
            source_type="calculation",
            source_id="response:expedite",
            description=(
                f"{total_recoverable_units} units are recoverable "
                f"through affected shipments across "
                f"{total_orders_helped} affected orders. "
                f"Estimated expedite cost uses the planning "
                f"assumption of ₹{EXPEDITE_COST_PER_UNIT:.2f} "
                f"per unit."
            ),
        )
    )

    return ResponseOption(
        option_type="EXPEDITE",
        title="Expedite disrupted shipments",
        description=(
            f"Accelerate affected incoming shipments to recover "
            f"up to {total_recoverable_units} units for "
            f"{total_orders_helped} affected orders."
        ),
        units_recovered=total_recoverable_units,
        orders_helped=total_orders_helped,
        estimated_cost=estimated_cost,
        tradeoff=(
            f"Estimated additional logistics cost of "
            f"₹{estimated_cost:,.0f}, but preserves inventory "
            f"at other warehouses and directly restores "
            f"incoming supply."
        ),
        feasible=(
            total_recoverable_units > 0
            and total_orders_helped > 0
        ),
        reason=(
            f"{total_recoverable_units} units from affected "
            f"incoming shipments can be mapped to "
            f"{total_orders_helped} affected customer orders."
        ),
        evidence=tuple(evidence),
    )


# ============================================================
# PART-SHIP
# ============================================================


def _generate_part_ship_option(
    impact: ImpactAssessment,
) -> ResponseOption:
    """
    Identify orders that can be partially fulfilled using
    inventory already available at their serving warehouse.
    """

    affected_orders = [
        order
        for order in impact.affected_orders
        if (
            0 < order.shortage_quantity < order.quantity
        )
    ]

    if not affected_orders:
        return ResponseOption(
            option_type="PART_SHIP",
            title="Part-ship affected orders",
            description=(
                "Ship currently available units now and "
                "deliver the remaining quantity later."
            ),
            units_recovered=0,
            orders_helped=0,
            estimated_cost=0.0,
            tradeoff=(
                "No affected order currently has enough "
                "available inventory for a partial shipment."
            ),
            feasible=False,
            reason=(
                "No affected customer order can currently "
                "be partially fulfilled."
            ),
            evidence=(),
        )

    affected_orders.sort(key=_order_sort_key)

    units_available_now = sum(
        order.quantity - order.shortage_quantity
        for order in affected_orders
    )

    evidence = tuple(
        _make_evidence(
            source_type="order",
            source_id=order.order_id,
            description=(
                f"{order.order_id} for {order.customer_name} "
                f"has {order.quantity - order.shortage_quantity} "
                f"units currently fulfillable and "
                f"{order.shortage_quantity} units exposed."
            ),
        )
        for order in affected_orders
    )

    evidence += (
        _make_evidence(
            source_type="calculation",
            source_id="response:part_ship",
            description=(
                f"{units_available_now} units can be shipped "
                f"immediately across {len(affected_orders)} "
                f"partially fulfillable orders."
            ),
        ),
    )

    return ResponseOption(
        option_type="PART_SHIP",
        title="Part-ship affected orders",
        description=(
            f"Ship {units_available_now} currently available "
            f"units now while the remaining quantities are "
            f"resolved separately."
        ),
        units_recovered=units_available_now,
        orders_helped=len(affected_orders),
        estimated_cost=0.0,
        tradeoff=(
            "Provides customers with available inventory sooner "
            "without additional recovery cost, but leaves "
            "the remaining quantities outstanding."
        ),
        feasible=(
            units_available_now > 0
            and len(affected_orders) > 0
        ),
        reason=(
            f"{len(affected_orders)} affected orders have "
            f"partial inventory available at their serving "
            f"warehouse."
        ),
        evidence=evidence,
    )


# ============================================================
# CUSTOMER NOTIFICATION
# ============================================================


def _generate_customer_notification_option(
    impact: ImpactAssessment,
) -> ResponseOption:
    """
    Generate a communication option for affected customers.

    Notification does not recover inventory. Its value is in
    reducing surprise and enabling human customer management.
    """

    affected_orders = _affected_orders_with_shortage(impact)

    if not affected_orders:
        return ResponseOption(
            option_type="CUSTOMER_NOTIFY",
            title="Notify affected customers",
            description=(
                "Communicate disruption-related fulfillment "
                "changes to affected customers."
            ),
            units_recovered=0,
            orders_helped=0,
            estimated_cost=0.0,
            tradeoff=(
                "No affected customer orders require notification."
            ),
            feasible=False,
            reason=(
                "No customer order has a currently quantified "
                "shortage."
            ),
            evidence=(),
        )

    evidence = tuple(
        _make_evidence(
            source_type="order",
            source_id=order.order_id,
            description=(
                f"{order.order_id} for {order.customer_name} "
                f"has {order.shortage_quantity} units at risk "
                f"with promised date "
                f"{order.promised_date or 'not specified'}."
            ),
        )
        for order in affected_orders
    )

    evidence += (
        _make_evidence(
            source_type="calculation",
            source_id="response:customer_notify",
            description=(
                f"{len(affected_orders)} affected customer "
                f"orders require communication based on the "
                f"current shortage assessment."
            ),
        ),
    )

    return ResponseOption(
        option_type="CUSTOMER_NOTIFY",
        title="Notify affected customers",
        description=(
            f"Communicate revised fulfillment expectations "
            f"for {len(affected_orders)} affected orders."
        ),
        units_recovered=0,
        orders_helped=len(affected_orders),
        estimated_cost=0.0,
        tradeoff=(
            "Does not recover inventory, but gives customers "
            "visibility and allows human teams to manage "
            "expectations before promised dates are missed."
        ),
        feasible=True,
        reason=(
            f"{len(affected_orders)} customer orders have "
            f"quantified exposure."
        ),
        evidence=evidence,
    )


# ============================================================
# REALLOCATION
# ============================================================


def _build_shortage_by_product_warehouse(
    affected_orders: list,
) -> dict[tuple[str, str], int]:
    """
    Calculate customer shortage by product and destination
    warehouse.
    """

    shortages: dict[tuple[str, str], int] = {}

    for order in affected_orders:

        if order.shortage_quantity <= 0:
            continue

        key = (
            order.product_id,
            order.warehouse_id,
        )

        shortages[key] = (
            shortages.get(key, 0)
            + order.shortage_quantity
        )

    return shortages


def _build_inventory_by_product(
    impact: ImpactAssessment,
) -> dict[str, list]:
    """
    Group inventory records by product.
    """

    inventory_by_product: dict[str, list] = {}

    for inventory in impact.inventory_impacts:
        inventory_by_product.setdefault(
            inventory.product_id,
            [],
        ).append(inventory)

    return inventory_by_product


def _find_reallocation_opportunities(
    impact: ImpactAssessment,
) -> list[ResponseOption]:
    """
    Find genuine warehouse-to-warehouse reallocation options.

    A source warehouse is considered a valid source only when it
    has available inventory beyond its own pending demand.

    A destination must have a quantified shortage.
    """

    affected_orders = _affected_orders_with_shortage(impact)

    if not affected_orders:
        return []

    shortage_by_destination = (
        _build_shortage_by_product_warehouse(
            affected_orders
        )
    )

    inventory_by_product = _build_inventory_by_product(
        impact
    )

    opportunities: list[ResponseOption] = []

    for product_id, inventories in inventory_by_product.items():

        destinations = {
            warehouse_id: shortage
            for (
                pid,
                warehouse_id,
            ), shortage in shortage_by_destination.items()
            if (
                pid == product_id
                and shortage > 0
            )
        }

        if not destinations:
            continue

        sources: list[tuple[Any, int]] = []

        for inventory in inventories:

            if inventory.warehouse_id in destinations:
                continue

            if inventory.available_quantity <= 0:
                continue

            source_pending_demand = sum(
                order.quantity
                for order in impact.affected_orders
                if (
                    order.product_id == product_id
                    and order.warehouse_id
                    == inventory.warehouse_id
                )
            )

            source_surplus = max(
                inventory.available_quantity
                - source_pending_demand,
                0,
            )

            if source_surplus > 0:
                sources.append(
                    (
                        inventory,
                        source_surplus,
                    )
                )

        if not sources:
            continue

        remaining_shortage = dict(destinations)

        for source, source_surplus in sources:

            remaining_source = source_surplus

            for destination_id in list(
                remaining_shortage.keys()
            ):

                if remaining_source <= 0:
                    break

                destination_shortage = (
                    remaining_shortage[destination_id]
                )

                if destination_shortage <= 0:
                    continue

                units_to_move = min(
                    remaining_source,
                    destination_shortage,
                )

                if units_to_move <= 0:
                    continue

                orders_helped = _count_orders_helped(
                    affected_orders=affected_orders,
                    product_id=product_id,
                    warehouse_id=destination_id,
                    available_units=units_to_move,
                )

                if orders_helped <= 0:
                    continue

                estimated_cost = (
                    units_to_move
                    * REALLOCATION_COST_PER_UNIT
                )

                evidence = (
                    _make_evidence(
                        source_type="inventory",
                        source_id=(
                            f"{source.warehouse_id}:"
                            f"{product_id}"
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
                            f"response:reallocate:"
                            f"{source.warehouse_id}:"
                            f"{destination_id}:"
                            f"{product_id}"
                        ),
                        description=(
                            f"{source.warehouse_name} has "
                            f"{source_surplus} units of estimated "
                            f"surplus after its pending demand. "
                            f"Destination warehouse "
                            f"{destination_id} has "
                            f"{destination_shortage} units "
                            f"of customer shortage."
                        ),
                    ),
                    _make_evidence(
                        source_type="calculation",
                        source_id=(
                            f"response:reallocate:cost:"
                            f"{source.warehouse_id}:"
                            f"{destination_id}:"
                            f"{product_id}"
                        ),
                        description=(
                            f"Estimated transfer cost is "
                            f"₹{estimated_cost:,.0f}, using the "
                            f"planning assumption of "
                            f"₹{REALLOCATION_COST_PER_UNIT:.2f} "
                            f"per transferred unit."
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
                            f"Transfer {units_to_move} units of "
                            f"{source.product_name} from "
                            f"{source.warehouse_name} to the "
                            f"warehouse serving affected orders."
                        ),
                        units_recovered=units_to_move,
                        orders_helped=orders_helped,
                        estimated_cost=estimated_cost,
                        tradeoff=(
                            f"Uses existing inventory instead of "
                            f"waiting for disrupted supply. "
                            f"Estimated transfer cost is "
                            f"₹{estimated_cost:,.0f} and reduces "
                            f"the source warehouse's inventory buffer."
                        ),
                        feasible=True,
                        reason=(
                            f"{source.warehouse_name} has "
                            f"{source_surplus} units of estimated "
                            f"surplus while destination "
                            f"{destination_id} has "
                            f"{destination_shortage} units "
                            f"of customer shortage."
                        ),
                        evidence=evidence,
                    )
                )

                remaining_source -= units_to_move
                remaining_shortage[destination_id] -= units_to_move

    return opportunities


# ============================================================
# RESPONSE OPTION GENERATION
# ============================================================


def generate_response_options(
    impact: ImpactAssessment,
) -> list[ResponseOption]:
    """
    Generate all response options supported by the current
    deterministic impact assessment.

    Important design rule:

        This function never parses the original disruption notice.

        It never guesses suppliers, products, orders, inventory,
        quantities, or warehouses.

        It only operates on resolved and quantified business
        impact supplied by ImpactAssessment.
    """

    # A disruption with no business impact must produce no
    # response actions.
    if not impact.has_impact:
        return []

    options: list[ResponseOption] = []

    # --------------------------------------------------------
    # 1. Expedite affected incoming supply
    # --------------------------------------------------------

    expedite_option = _generate_expedite_option(
        impact
    )

    options.append(expedite_option)

    # --------------------------------------------------------
    # 2. Part-ship orders using available inventory
    # --------------------------------------------------------

    part_ship_option = _generate_part_ship_option(
        impact
    )

    options.append(part_ship_option)

    # --------------------------------------------------------
    # 3. Communicate with affected customers
    # --------------------------------------------------------

    notification_option = (
        _generate_customer_notification_option(
            impact
        )
    )

    options.append(notification_option)

    # --------------------------------------------------------
    # 4. Reallocate genuine surplus inventory
    # --------------------------------------------------------

    options.extend(
        _find_reallocation_opportunities(
            impact
        )
    )

    return options