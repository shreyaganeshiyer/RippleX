from __future__ import annotations
from datetime import date

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from backend.database import (
    get_inventory,
    get_orders,
    get_shipments,
)
from backend.entity_resolver import ResolvedDisruption


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """
    A traceable explanation for an impact claim.

    Every important number produced by the impact engine should be explainable
    through underlying database records.
    """

    source_type: str
    source_id: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AffectedShipment:
    shipment_id: str
    supplier_id: str
    supplier_name: str
    product_id: str
    product_name: str
    quantity: int
    warehouse_id: str
    warehouse_name: str
    expected_date: str
    status: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [
            evidence.to_dict() for evidence in self.evidence
        ]
        return result


@dataclass(frozen=True)
class InventoryImpact:
    product_id: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    quantity_on_hand: int
    reserved_quantity: int
    available_quantity: int
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [
            evidence.to_dict() for evidence in self.evidence
        ]
        return result


@dataclass(frozen=True)
class ProductImpact:
    product_id: str
    product_name: str
    affected_shipment_quantity: int
    available_inventory: int
    pending_order_quantity: int
    shortage_quantity: int
    affected_order_count: int
    has_shortage: bool
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [
            evidence.to_dict() for evidence in self.evidence
        ]
        return result


@dataclass(frozen=True)
class AffectedOrder:
    order_id: str
    customer_name: str
    product_id: str
    product_name: str
    quantity: int
    warehouse_id: str
    warehouse_name: str
    promised_date: str
    priority: str
    order_value: float
    order_value_at_risk: float
    urgency_score: float
    risk_reason: str
    status: str
    shortage_quantity: int
    impact_status: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [
            evidence.to_dict() for evidence in self.evidence
        ]
        return result


@dataclass(frozen=True)
class ImpactAssessment:
    """
    Complete deterministic assessment of a disruption.

    This object contains only facts calculated from the disruption event and
    the company's database. No LLM-generated business impact is stored here.
    """

    has_impact: bool
    summary: str

    affected_products: tuple[ProductImpact, ...]
    affected_shipments: tuple[AffectedShipment, ...]
    inventory_impacts: tuple[InventoryImpact, ...]
    affected_orders: tuple[AffectedOrder, ...]

    total_orders_at_risk: int
    total_units_at_risk: int
    total_order_value_at_risk: float

    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_impact": self.has_impact,
            "summary": self.summary,
            "affected_products": [
                product.to_dict()
                for product in self.affected_products
            ],
            "affected_shipments": [
                shipment.to_dict()
                for shipment in self.affected_shipments
            ],
            "inventory_impacts": [
                inventory.to_dict()
                for inventory in self.inventory_impacts
            ],
            "affected_orders": [
                order.to_dict()
                for order in self.affected_orders
            ],
            "total_orders_at_risk": self.total_orders_at_risk,
            "total_units_at_risk": self.total_units_at_risk,
            "total_order_value_at_risk": self.total_order_value_at_risk,
            "evidence": [
                evidence.to_dict()
                for evidence in self.evidence
            ],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(value: Any) -> int:
    """Convert a database value to a non-negative integer."""

    if value is None:
        return 0

    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    """Convert a database value to a float."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _row_to_dict(row: Any) -> dict[str, Any]:
    """
    Convert sqlite3.Row or a normal mapping into a dictionary.
    """

    if row is None:
        return {}

    if isinstance(row, dict):
        return dict(row)

    try:
        return dict(row)
    except (TypeError, ValueError):
        raise TypeError(
            f"Unsupported database row type: {type(row).__name__}"
        )


def _make_evidence(
    source_type: str,
    source_id: str,
    description: str,
) -> Evidence:
    return Evidence(
        source_type=source_type,
        source_id=source_id,
        description=description,
    )


# ---------------------------------------------------------------------------
# Shipment tracing
# ---------------------------------------------------------------------------

def _find_affected_shipments(
    disruption: ResolvedDisruption,
) -> list[AffectedShipment]:
    """
    Find shipments that are actually connected to the resolved disruption.

    A shipment is considered affected only when:
      1. It belongs to the disrupted supplier.
      2. Its product was explicitly resolved as affected.
      3. It is an active/incoming shipment rather than a completed one.
    """

    if disruption.supplier is None or not disruption.supplier.resolved:
        return []

    supplier_id = disruption.supplier.entity_id

    if not supplier_id:
        return []

    product_ids = {
        product.product_id
        for product in disruption.products
    }

    if not product_ids:
        return []

    explicit_shipment_ids = set(
        disruption.affected_shipment_ids
    )

    shipments = get_shipments(supplier_id=supplier_id)

    affected: list[AffectedShipment] = []

    for shipment_row in shipments:
        shipment = _row_to_dict(shipment_row)

        shipment_id = str(shipment.get("shipment_id") or "")
        product_id = shipment.get("product_id")

        if explicit_shipment_ids and shipment_id not in explicit_shipment_ids:
            continue

        if product_id not in product_ids:
            continue

        status = str(shipment.get("status") or "").upper()

        # Completed/cancelled shipments cannot create future disruption impact.
        if status in {"DELIVERED", "COMPLETED", "CANCELLED"}:
            continue

        supplier_name = str(
            shipment.get("supplier_name")
            or disruption.supplier.entity_name
            or ""
        )
        product_name = str(shipment.get("product_name") or "")
        warehouse_name = str(shipment.get("warehouse_name") or "")

        quantity = _safe_int(shipment.get("quantity"))

        evidence = (
            _make_evidence(
                source_type="shipment",
                source_id=shipment_id,
                description=(
                    f"Shipment {shipment_id} contains {quantity} units of "
                    f"{product_name} from {supplier_name} and is currently "
                    f"not completed."
                ),
            ),
        )

        affected.append(
            AffectedShipment(
                shipment_id=shipment_id,
                supplier_id=str(shipment.get("supplier_id") or ""),
                supplier_name=supplier_name,
                product_id=str(product_id),
                product_name=product_name,
                quantity=quantity,
                warehouse_id=str(shipment.get("warehouse_id") or ""),
                warehouse_name=warehouse_name,
                expected_date=str(
                    shipment.get("expected_date") or ""
                ),
                status=status,
                evidence=evidence,
            )
        )

    return affected

def _find_warehouse_shipments(
    disruption: ResolvedDisruption,
) -> list[AffectedShipment]:
    """
    Find active incoming shipments destined for the disrupted warehouse.
    """

    if disruption.warehouse is None or not disruption.warehouse.resolved:
        return []

    warehouse_id = disruption.warehouse.entity_id

    if not warehouse_id:
        return []

    shipments = get_shipments()

    affected: list[AffectedShipment] = []

    for shipment_row in shipments:
        shipment = _row_to_dict(shipment_row)

        if str(shipment.get("warehouse_id") or "") != warehouse_id:
            continue

        status = str(
            shipment.get("status") or ""
        ).upper()

        if status in {"DELIVERED", "COMPLETED", "CANCELLED"}:
            continue

        shipment_id = str(
            shipment.get("shipment_id") or ""
        )

        quantity = _safe_int(
            shipment.get("quantity")
        )

        supplier_name = str(
            shipment.get("supplier_name") or ""
        )

        product_name = str(
            shipment.get("product_name") or ""
        )

        warehouse_name = str(
            shipment.get("warehouse_name") or ""
        )

        evidence = (
            _make_evidence(
                source_type="shipment",
                source_id=shipment_id,
                description=(
                    f"Shipment {shipment_id} contains {quantity} units "
                    f"of {product_name} destined for "
                    f"{warehouse_name} and is currently not completed."
                ),
            ),
        )

        affected.append(
            AffectedShipment(
                shipment_id=shipment_id,
                supplier_id=str(
                    shipment.get("supplier_id") or ""
                ),
                supplier_name=supplier_name,
                product_id=str(
                    shipment.get("product_id") or ""
                ),
                product_name=product_name,
                quantity=quantity,
                warehouse_id=warehouse_id,
                warehouse_name=warehouse_name,
                expected_date=str(
                    shipment.get("expected_date") or ""
                ),
                status=status,
                evidence=evidence,
            )
        )

    return affected

# ---------------------------------------------------------------------------
# Inventory tracing
# ---------------------------------------------------------------------------

def _find_inventory_impacts(
    product_ids: set[str],
) -> list[InventoryImpact]:
    """
    Retrieve current inventory for all affected products.
    """

    impacts: list[InventoryImpact] = []

    for product_id in sorted(product_ids):
        inventory_rows = get_inventory(product_id)

        for inventory_row in inventory_rows:
            inventory = _row_to_dict(inventory_row)

            warehouse_id = str(
                inventory.get("warehouse_id") or ""
            )

            warehouse_name = str(
                inventory.get("warehouse_name") or ""
            )

            product_name = str(
                inventory.get("product_name") or ""
            )

            quantity_on_hand = _safe_int(
                inventory.get("quantity")
            )

            reserved_quantity = _safe_int(
                inventory.get("reserved_quantity")
            )

            available_quantity = _safe_int(
                inventory.get("available_quantity")
            )

            evidence = (
                _make_evidence(
                    source_type="inventory",
                    source_id=(
                        f"{warehouse_id}:{product_id}"
                    ),
                    description=(
                        f"{warehouse_name} has {quantity_on_hand} units "
                        f"of {product_name} on hand, {reserved_quantity} "
                        f"reserved, leaving {available_quantity} available."
                    ),
                ),
            )

            impacts.append(
                InventoryImpact(
                    product_id=str(product_id),
                    product_name=product_name,
                    warehouse_id=warehouse_id,
                    warehouse_name=warehouse_name,
                    quantity_on_hand=quantity_on_hand,
                    reserved_quantity=reserved_quantity,
                    available_quantity=available_quantity,
                    evidence=evidence,
                )
            )

    return impacts


def _find_warehouse_inventory_impacts(
    warehouse_id: str,
) -> list[InventoryImpact]:
    """
    Retrieve current inventory held at the disrupted warehouse.
    """

    impacts: list[InventoryImpact] = []

    # The database API is product-based, so inspect products represented
    # in the warehouse through the inventory records.
    from backend.database import get_all_products

    for product in get_all_products():
        product_id = str(product["product_id"])

        for inventory_row in get_inventory(product_id):
            inventory = _row_to_dict(inventory_row)

            if str(inventory.get("warehouse_id") or "") != warehouse_id:
                continue

            warehouse_name = str(
                inventory.get("warehouse_name") or ""
            )
            product_name = str(
                inventory.get("product_name") or ""
            )

            quantity_on_hand = _safe_int(
                inventory.get("quantity")
            )

            reserved_quantity = _safe_int(
                inventory.get("reserved_quantity")
            )

            available_quantity = _safe_int(
                inventory.get("available_quantity")
            )

            evidence = (
                _make_evidence(
                    source_type="inventory",
                    source_id=f"{warehouse_id}:{product_id}",
                    description=(
                        f"{warehouse_name} has {quantity_on_hand} units "
                        f"of {product_name} on hand, {reserved_quantity} "
                        f"reserved, leaving {available_quantity} available."
                    ),
                ),
            )

            impacts.append(
                InventoryImpact(
                    product_id=product_id,
                    product_name=product_name,
                    warehouse_id=warehouse_id,
                    warehouse_name=warehouse_name,
                    quantity_on_hand=quantity_on_hand,
                    reserved_quantity=reserved_quantity,
                    available_quantity=available_quantity,
                    evidence=evidence,
                )
            )

    return impacts

# ---------------------------------------------------------------------------
# Order tracing
# ---------------------------------------------------------------------------

def _find_affected_orders(
    product_ids: set[str],
) -> list[dict[str, Any]]:
    """
    Retrieve all pending customer orders for affected products.
    """

    orders: list[dict[str, Any]] = []

    for product_id in sorted(product_ids):
        order_rows = get_orders(product_id=product_id)

        for order_row in order_rows:
            order = _row_to_dict(order_row)

            status = str(
                order.get("status") or ""
            ).upper()

            if status != "PENDING":
                continue

            orders.append(order)

    return orders


def _find_warehouse_orders(
    warehouse_id: str,
) -> list[dict[str, Any]]:
    """
    Retrieve pending customer orders assigned to the disrupted warehouse.
    """

    orders: list[dict[str, Any]] = []

    from backend.database import get_all_products

    for product in get_all_products():
        product_id = str(product["product_id"])

        for order_row in get_orders(product_id=product_id):
            order = _row_to_dict(order_row)

            if str(order.get("warehouse_id") or "") != warehouse_id:
                continue

            status = str(
                order.get("status") or ""
            ).upper()

            if status != "PENDING":
                continue

            orders.append(order)

    return orders

# ---------------------------------------------------------------------------
# Impact calculation
# ---------------------------------------------------------------------------

def _calculate_available_inventory_by_product(
    inventory_impacts: list[InventoryImpact],
) -> dict[str, int]:
    """
    Aggregate available inventory across warehouses by product.

    This represents stock that is physically available now, not stock that
    would arrive through the disrupted shipments.
    """

    result: dict[str, int] = {}

    for inventory in inventory_impacts:
        result[inventory.product_id] = (
            result.get(inventory.product_id, 0)
            + inventory.available_quantity
        )

    return result


def _calculate_orders_by_product(
    orders: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}

    for order in orders:
        product_id = str(order.get("product_id") or "")

        if not product_id:
            continue

        result.setdefault(product_id, []).append(order)

    return result


def _calculate_product_impacts(
    product_ids: set[str],
    affected_shipments: list[AffectedShipment],
    inventory_impacts: list[InventoryImpact],
    orders: list[dict[str, Any]],
) -> list[ProductImpact]:
    """
    Calculate product-level supply exposure.

    Inventory is evaluated per warehouse.
    Stock in one warehouse cannot automatically satisfy
    orders assigned to another warehouse.
    """

    shipment_quantity_by_product: dict[str, int] = {}

    for shipment in affected_shipments:
        shipment_quantity_by_product[shipment.product_id] = (
            shipment_quantity_by_product.get(shipment.product_id, 0)
            + shipment.quantity
        )

    # Available inventory by (product, warehouse)
    available_inventory_by_product_and_warehouse: dict[
        tuple[str, str], int
    ] = {}

    for inventory in inventory_impacts:
        key = (
            inventory.product_id,
            inventory.warehouse_id,
        )

        available_inventory_by_product_and_warehouse[key] = (
            available_inventory_by_product_and_warehouse.get(key, 0)
            + inventory.available_quantity
        )

    orders_by_product = _calculate_orders_by_product(orders)

    impacts: list[ProductImpact] = []

    for product_id in sorted(product_ids):

        product_orders = orders_by_product.get(
            product_id,
            [],
        )

        pending_order_quantity = sum(
            _safe_int(order.get("quantity"))
            for order in product_orders
        )

        # Group demand by warehouse
        warehouse_demand: dict[str, int] = {}

        for order in product_orders:
            warehouse_id = str(
                order.get("warehouse_id") or ""
            )

            warehouse_demand[warehouse_id] = (
                warehouse_demand.get(warehouse_id, 0)
                + _safe_int(order.get("quantity"))
            )

        # Calculate shortage independently for each warehouse
        shortage_quantity = 0
        available_inventory = 0

        for warehouse_id, demand in warehouse_demand.items():

            warehouse_available = (
                available_inventory_by_product_and_warehouse.get(
                    (product_id, warehouse_id),
                    0,
                )
            )

            available_inventory += warehouse_available

            warehouse_shortage = max(
                demand - warehouse_available,
                0,
            )

            shortage_quantity += warehouse_shortage

        product_name = ""

        for inventory in inventory_impacts:
            if inventory.product_id == product_id:
                product_name = inventory.product_name
                break

        if not product_name:
            for shipment in affected_shipments:
                if shipment.product_id == product_id:
                    product_name = shipment.product_name
                    break

        evidence: list[Evidence] = []

        evidence.append(
            _make_evidence(
                source_type="calculation",
                source_id=f"product:{product_id}",
                description=(
                    f"Product {product_name}: "
                    f"{available_inventory} available units "
                    f"at warehouses serving pending orders "
                    f"versus {pending_order_quantity} units "
                    f"of pending demand. "
                    f"Shortage is calculated independently "
                    f"by warehouse. Disrupted incoming shipments "
                    f"totaling "
                    f"{shipment_quantity_by_product.get(product_id, 0)} "
                    f"units are excluded from available supply."
                ),
            )
        )

        impacts.append(
            ProductImpact(
                product_id=product_id,
                product_name=product_name,
                affected_shipment_quantity=(
                    shipment_quantity_by_product.get(
                        product_id,
                        0,
                    )
                ),
                available_inventory=available_inventory,
                pending_order_quantity=pending_order_quantity,
                shortage_quantity=shortage_quantity,
                affected_order_count=len(product_orders),
                has_shortage=shortage_quantity > 0,
                evidence=tuple(evidence),
            )
        )

    return impacts


# ---------------------------------------------------------------------------
# Order-level impact
# ---------------------------------------------------------------------------

def _calculate_urgency_score(order: dict[str, Any]) -> float:
    """
    Calculate a deterministic urgency score.

    Higher score = more urgent.
    """

    priority_scores = {
        "HIGH": 60,
        "MEDIUM": 35,
        "LOW": 15,
    }

    priority = str(
        order.get("priority") or ""
    ).upper()

    score = priority_scores.get(priority, 5)

    # Earlier promised dates are more urgent.
    promised_date = str(
        order.get("promised_date") or ""
    )

    if promised_date:
        try:
            promised = date.fromisoformat(promised_date)
            days_until_due = (
                promised - date.today()
            ).days

            if days_until_due <= 2:
                score += 30
            elif days_until_due <= 5:
                score += 20
            elif days_until_due <= 10:
                score += 10

        except ValueError:
            pass

    # Higher-value orders get a smaller additional boost.
    order_value = _safe_float(
        order.get("order_value")
    )

    if order_value >= 30000:
        score += 10
    elif order_value >= 15000:
        score += 5

    return float(score)





def _calculate_order_impacts(
    orders: list[dict[str, Any]],
    product_impacts: list[ProductImpact],
) -> list[AffectedOrder]:
    """
    Determine which individual pending orders are exposed.

    Shortages are calculated independently for each
    (product, warehouse) pair. Inventory from another warehouse
    cannot automatically satisfy these orders.
    """

    # ---------------------------------------------------------------
    # Group orders by (product, warehouse)
    # ---------------------------------------------------------------

    orders_by_product_and_warehouse: dict[
        tuple[str, str],
        list[dict[str, Any]]
    ] = {}

    for order in orders:
        product_id = str(order.get("product_id") or "")
        warehouse_id = str(order.get("warehouse_id") or "")

        if not product_id or not warehouse_id:
            continue

        key = (product_id, warehouse_id)

        orders_by_product_and_warehouse.setdefault(
            key,
            []
        ).append(order)

    # ---------------------------------------------------------------
    # Calculate available inventory by (product, warehouse)
    #
    # We derive this from the product impacts' evidence-independent
    # inputs passed into this function by calculating the shortage
    # from the product impact only where possible.
    #
    # Instead, the product-level shortage is NOT redistributed.
    # We determine the actual warehouse shortage from the order
    # allocation logic below.
    # ---------------------------------------------------------------

    shortage_by_product = {
        impact.product_id: impact.shortage_quantity
        for impact in product_impacts
    }

    # ---------------------------------------------------------------
    # IMPORTANT:
    #
    # ProductImpact.shortage_quantity is already the SUM of actual
    # warehouse shortages.
    #
    # We need to preserve those warehouse shortages rather than
    # proportionally redistributing them.
    #
    # The deterministic allocation is therefore based on the order
    # groups, with the total shortage constrained to the product's
    # actual shortage.
    #
    # To avoid falsely moving shortage between warehouses, process
    # warehouses in deterministic order and only allocate shortage
    # where the product impact actually indicates exposure.
    # ---------------------------------------------------------------

    affected_orders: list[AffectedOrder] = []

    priority_rank = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
    }

    # ---------------------------------------------------------------
    # Build warehouse-level demand.
    # ---------------------------------------------------------------

    demand_by_product_and_warehouse: dict[
        tuple[str, str],
        int
    ] = {}

    for key, warehouse_orders in orders_by_product_and_warehouse.items():
        demand_by_product_and_warehouse[key] = sum(
            _safe_int(order.get("quantity"))
            for order in warehouse_orders
        )

    # ---------------------------------------------------------------
    # We need the actual inventory numbers to calculate the exact
    # warehouse shortage.
    #
    # ProductImpact does not contain warehouse-level inventory, so
    # reconstruct the available quantity from the database.
    # ---------------------------------------------------------------

    from backend.database import get_inventory

    available_by_product_and_warehouse: dict[
        tuple[str, str],
        int
    ] = {}

    product_ids = {
        product_id
        for product_id, _ in orders_by_product_and_warehouse
    }

    for product_id in sorted(product_ids):
        inventory_rows = get_inventory(product_id)

        for inventory_row in inventory_rows:
            inventory = _row_to_dict(inventory_row)

            warehouse_id = str(
                inventory.get("warehouse_id") or ""
            )

            available_quantity = _safe_int(
                inventory.get("available_quantity")
            )

            key = (product_id, warehouse_id)

            available_by_product_and_warehouse[key] = (
                available_by_product_and_warehouse.get(key, 0)
                + available_quantity
            )

    # ---------------------------------------------------------------
    # Calculate ACTUAL shortage independently for every warehouse.
    # ---------------------------------------------------------------

    warehouse_shortage: dict[
        tuple[str, str],
        int
    ] = {}

    for key, demand in demand_by_product_and_warehouse.items():
        available = available_by_product_and_warehouse.get(
            key,
            0,
        )

        warehouse_shortage[key] = max(
            demand - available,
            0,
        )

    # ---------------------------------------------------------------
    # Allocate each warehouse's actual shortage to its orders.
    # ---------------------------------------------------------------

    for key in sorted(orders_by_product_and_warehouse.keys()):

        product_id, warehouse_id = key

        remaining_shortage = warehouse_shortage.get(
            key,
            0,
        )

        if remaining_shortage <= 0:
            continue

        warehouse_orders = sorted(
            orders_by_product_and_warehouse[key],
            key=lambda order: (
                priority_rank.get(
                    str(order.get("priority") or "").upper(),
                    3,
                ),
                str(
                    order.get("promised_date")
                    or "9999-12-31"
                ),
                -_safe_float(
                    order.get("order_value")
                ),
                str(
                    order.get("order_id")
                    or ""
                ),
            ),
        )

        # -----------------------------------------------------------
        # Allocate scarce inventory to the most urgent orders first.
        # -----------------------------------------------------------

        for order in warehouse_orders:

            if remaining_shortage <= 0:
                break

            quantity = _safe_int(
                order.get("quantity")
            )

            if quantity <= 0:
                continue

            order_shortage = min(
                quantity,
                remaining_shortage,
            )

            remaining_shortage -= order_shortage

            order_id = str(
                order.get("order_id") or ""
            )

            customer_name = str(
                order.get("customer_name") or ""
            )

            product_name = str(
                order.get("product_name") or ""
            )

            warehouse_name = str(
                order.get("warehouse_name") or ""
            )

            evidence = (
                _make_evidence(
                    source_type="order",
                    source_id=order_id,
                    description=(
                        f"Order {order_id} requires "
                        f"{quantity} units of "
                        f"{product_name}."
                    ),
                ),
                _make_evidence(
                    source_type="inventory",
                    source_id=(
                        f"{warehouse_id}:{product_id}"
                    ),
                    description=(
                        f"{warehouse_name} has "
                        f"{available_by_product_and_warehouse.get(key, 0)} "
                        f"available units of {product_name}, "
                        f"while orders assigned to this warehouse "
                        f"require {demand_by_product_and_warehouse[key]} "
                        f"units."
                    ),
                ),
                _make_evidence(
                    source_type="calculation",
                    source_id=(
                        f"order-impact:{order_id}"
                    ),
                    description=(
                        f"{order_shortage} units of Order "
                        f"{order_id} are exposed because "
                        f"the assigned warehouse has "
                        f"insufficient available inventory."
                    ),
                ),
            )

            affected_orders.append(
                AffectedOrder(
                    order_id=order_id,
                    customer_name=customer_name,
                    product_id=product_id,
                    product_name=product_name,
                    quantity=quantity,
                    warehouse_id=warehouse_id,
                    warehouse_name=warehouse_name,
                    promised_date=str(
                        order.get("promised_date") or ""
                    ),
                    priority=str(
                        order.get("priority") or ""
                    ),
                    order_value=_safe_float(
                        order.get("order_value")
                    ),
                    order_value_at_risk=(
                        _safe_float(
                            order.get("order_value")
                        )
                        * order_shortage
                        / quantity
                        if quantity > 0
                        else 0.0
                    ),
                    urgency_score=_calculate_urgency_score(
                        order
                    ),
                    risk_reason=(
                        f"{str(order.get('priority') or 'UNKNOWN').upper()} "
                        f"priority order with "
                        f"{order_shortage} units exposed."
                    ),
                    status=str(
                        order.get("status") or ""
                    ).upper(),
                    shortage_quantity=order_shortage,
                    impact_status="AT_RISK",
                    evidence=evidence,
                )
            )

    # ---------------------------------------------------------------
    # Highest urgency first
    # ---------------------------------------------------------------

    affected_orders.sort(
        key=lambda order: (
            -order.urgency_score,
            order.promised_date or "9999-12-31",
            -order.order_value_at_risk,
            order.order_id,
        )
    )

    return affected_orders


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_impact(
    disruption: ResolvedDisruption,
) -> ImpactAssessment:
    """
    Calculate the deterministic business impact of a resolved disruption.

    Rules:
      - unresolved supplier => no calculated impact
      - unresolved/conflicting products => no impact for those products
      - only verified database entities are traced
      - completed shipments are ignored
      - only pending customer orders are considered
      - disrupted incoming shipments are excluded from available supply
      - no LLM is called
      - no business action is taken
    """

    # ---------------------------------------------------------------
    # Safety gate
    # ---------------------------------------------------------------

    if disruption.requires_human_review:
        return ImpactAssessment(
            has_impact=False,
            summary=(
                "Impact assessment could not be completed because one or "
                "more disruption entities require human review."
            ),
            affected_products=tuple(),
            affected_shipments=tuple(),
            inventory_impacts=tuple(),
            affected_orders=tuple(),
            total_orders_at_risk=0,
            total_units_at_risk=0,
            total_order_value_at_risk=0.0,
            evidence=(
                _make_evidence(
                    source_type="resolution",
                    source_id="human-review",
                    description=(
                        "Entity resolution produced an unresolved or "
                        "conflicting entity. No business impact was "
                        "inferred."
                    ),
                ),
            ),
        )

    is_warehouse_disruption = (
    disruption.warehouse is not None
    and disruption.warehouse.resolved
        )

    if not is_warehouse_disruption and (
            disruption.supplier is None
            or not disruption.supplier.resolved
        ):
        return ImpactAssessment(
            has_impact=False,
            summary=(
                "No impact identified because the disruption could not be "
                "mapped to a verified supplier."
            ),
            affected_products=tuple(),
            affected_shipments=tuple(),
            inventory_impacts=tuple(),
            affected_orders=tuple(),
            total_orders_at_risk=0,
            total_units_at_risk=0,
            total_order_value_at_risk=0.0,
            evidence=(
                _make_evidence(
                    source_type="resolution",
                    source_id="supplier-unresolved",
                    description=(
                        "Supplier could not be deterministically mapped "
                        "to the company's database."
                    ),
                ),
            ),
        )

    product_ids = {
        product.product_id
        for product in disruption.products
        if product.product_id
    }

    if is_warehouse_disruption:
        warehouse = disruption.warehouse
        if warehouse is None:
            return ImpactAssessment(
                has_impact=False,
                summary="No impact identified because the warehouse could not be mapped to company data.",
                affected_products=(), affected_shipments=(),
                inventory_impacts=(), affected_orders=(),
                total_orders_at_risk=0, total_units_at_risk=0,
                total_order_value_at_risk=0.0, evidence=(),
            )

        warehouse_id = warehouse.entity_id
        if warehouse_id is None:
            return ImpactAssessment(
                has_impact=False,
                summary="No impact identified because the warehouse ID could not be resolved.",
                affected_products=(), affected_shipments=(),
                inventory_impacts=(), affected_orders=(),
                total_orders_at_risk=0, total_units_at_risk=0,
                total_order_value_at_risk=0.0, evidence=(),
            )

        inventory_impacts = _find_warehouse_inventory_impacts(warehouse_id)
        affected_shipments = _find_warehouse_shipments(disruption)
        orders = _find_warehouse_orders(warehouse_id)

        product_ids.update(
            inventory.product_id for inventory in inventory_impacts
        )
        product_ids.update(
            shipment.product_id for shipment in affected_shipments
        )
        product_ids.update(
            str(order.get("product_id"))
            for order in orders
            if order.get("product_id")
        )
    else:
        if not product_ids:
            return ImpactAssessment(
                has_impact=False,
                summary=(
                    "No impact identified because no affected products were "
                    "successfully mapped to company data."
                ),
                affected_products=tuple(),
                affected_shipments=tuple(),
                inventory_impacts=tuple(),
                affected_orders=tuple(),
                total_orders_at_risk=0,
                total_units_at_risk=0,
                total_order_value_at_risk=0.0,
                evidence=(
                    _make_evidence(
                        source_type="resolution",
                        source_id="products-unresolved",
                        description=(
                            "No affected products could be deterministically "
                            "mapped to the company's database."
                        ),
                    ),
                ),
            )

    # ---------------------------------------------------------------
    # Trace supply chain
    # ---------------------------------------------------------------

    if not is_warehouse_disruption:
        affected_shipments = _find_affected_shipments(
            disruption
        )

        inventory_impacts = _find_inventory_impacts(
            product_ids
        )

        orders = _find_affected_orders(
            product_ids
        )

    # ---------------------------------------------------------------
    # Calculate product impact
    # ---------------------------------------------------------------

    product_impacts = _calculate_product_impacts(
        product_ids=product_ids,
        affected_shipments=affected_shipments,
        inventory_impacts=inventory_impacts,
        orders=orders,
    )

    # ---------------------------------------------------------------
    # Calculate order impact
    # ---------------------------------------------------------------

    affected_orders = _calculate_order_impacts(
        orders=orders,
        product_impacts=product_impacts,
    )

    # ---------------------------------------------------------------
    # Aggregate totals
    # ---------------------------------------------------------------

    total_orders_at_risk = len(
        affected_orders
    )

    total_units_at_risk = sum(
        order.shortage_quantity
        for order in affected_orders
    )

    total_order_value_at_risk = sum(
    order.order_value_at_risk
    for order in affected_orders
)

    has_impact = (
    total_orders_at_risk > 0
    or (
        len(affected_shipments) > 0
        and is_warehouse_disruption
    )
    )

    # ---------------------------------------------------------------
    # Build summary
    # ---------------------------------------------------------------

    if has_impact:
        summary = (
            f"{total_orders_at_risk} pending customer orders are at risk "
            f"across {total_units_at_risk} units. "
            f"{len(affected_shipments)} incoming shipment(s) are affected."
        )
    elif affected_shipments:
        summary = (
            f"{len(affected_shipments)} shipment(s) are affected, "
            "but current available inventory is sufficient to cover "
            "the pending orders identified."
        )
    else:
        summary = (
            "No current business impact identified. "
            "The disruption does not map to any active shipment that "
            "currently exposes pending customer orders."
        )

    # ---------------------------------------------------------------
    # Top-level evidence
    # ---------------------------------------------------------------

    evidence: list[Evidence] = []

    for shipment in affected_shipments:
        evidence.extend(shipment.evidence)

    for product in product_impacts:
        evidence.extend(product.evidence)

    for order in affected_orders:
        evidence.extend(order.evidence)

    return ImpactAssessment(
        has_impact=has_impact,
        summary=summary,
        affected_products=tuple(product_impacts),
        affected_shipments=tuple(affected_shipments),
        inventory_impacts=tuple(inventory_impacts),
        affected_orders=tuple(affected_orders),
        total_orders_at_risk=total_orders_at_risk,
        total_units_at_risk=total_units_at_risk,
        total_order_value_at_risk=round(
            total_order_value_at_risk,
            2,
        ),
        evidence=tuple(evidence),
    )


# ---------------------------------------------------------------------------
# Human-readable test output
# ---------------------------------------------------------------------------

def print_assessment(
    assessment: ImpactAssessment,
) -> None:
    """
    Print an easy-to-read representation for local development/testing.
    """

    print("\nRippleX Impact Assessment")
    print("=" * 60)

    print(f"Has impact: {assessment.has_impact}")
    print(f"Summary: {assessment.summary}")

    print("\nAffected shipments:")
    if assessment.affected_shipments:
        for shipment in assessment.affected_shipments:
            print(
                f"  - {shipment.shipment_id}: "
                f"{shipment.product_name} "
                f"({shipment.quantity} units) → "
                f"{shipment.warehouse_name}"
            )
    else:
        print("  None")

    print("\nProduct impact:")

    if assessment.affected_products:
        for product in assessment.affected_products:
            print(
                f"  - {product.product_name}: "
                f"available={product.available_inventory}, "
                f"demand={product.pending_order_quantity}, "
                f"shortage={product.shortage_quantity}"
            )
    else:
        print("  None")

    print("\nAffected orders:")

    if assessment.affected_orders:
        for order in assessment.affected_orders:
            print(
                f"  - {order.order_id}: "
                f"{order.customer_name} | "
                f"{order.product_name} | "
                f"{order.quantity} units | "
                f"shortage={order.shortage_quantity} | "
                f"priority={order.priority} | "
                f"urgency={order.urgency_score:.0f} | "
                f"value=₹{order.order_value_at_risk:,.2f} at risk"
            )
    else:
        print("  None")

    print("\nTotals:")
    print(
        f"  Orders at risk: "
        f"{assessment.total_orders_at_risk}"
    )
    print(
        f"  Units at risk: "
        f"{assessment.total_units_at_risk}"
    )
    print(
        f"  Order value at risk: "
        f"₹{assessment.total_order_value_at_risk:,.2f}"
    )

    print("\nEvidence:")
    for evidence in assessment.evidence:
        print(
            f"  - [{evidence.source_type}] "
            f"{evidence.source_id}: "
            f"{evidence.description}"
        )


# ---------------------------------------------------------------------------
# Local tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from backend.disruption_parser import DisruptionEvent
    from backend.entity_resolver import resolve_disruption

    print("\n" + "=" * 60)
    print("TEST 1 — Real disruption")
    print("=" * 60)

    event = DisruptionEvent(
        event_type="supplier_production_halt",
        supplier_name="ABC Components",
        location="Bangalore",
        affected_products=[
            "X-200",
            "X-300",
        ],
        delay_days=10,
        summary=(
            "ABC Components' Bangalore facility has stopped "
            "dispatching X-200 and X-300 for approximately 10 days."
        ),
        confidence=0.95,
    )

    resolved = resolve_disruption(event)

    assessment = assess_impact(resolved)

    print_assessment(assessment)

    print("\n" + "=" * 60)
    print("TEST 2 — Unknown supplier")
    print("=" * 60)

    unknown_event = DisruptionEvent(
        event_type="supplier_production_halt",
        supplier_name="NovaTech Industries",
        location="Bangalore",
        affected_products=["Q-999"],
        delay_days=10,
        summary="Unknown supplier reports a production halt.",
        confidence=0.90,
    )

    unknown_resolved = resolve_disruption(
        unknown_event
    )

    unknown_assessment = assess_impact(
        unknown_resolved
    )

    print_assessment(unknown_assessment)

    print("\n" + "=" * 60)
    print("TEST 3 — Ambiguous product")
    print("=" * 60)

    ambiguous_event = DisruptionEvent(
        event_type="supplier_delay",
        supplier_name="ABC Components",
        location="Bangalore",
        affected_products=["X-series"],
        delay_days=5,
        summary=(
            "ABC Components reports delays affecting the X-series."
        ),
        confidence=0.70,
    )

    ambiguous_resolved = resolve_disruption(
        ambiguous_event
    )

    ambiguous_assessment = assess_impact(
        ambiguous_resolved
    )

    print_assessment(ambiguous_assessment)
