from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from backend.database import (
    get_product,
    get_product_by_name,
    get_shipments,
    get_supplier,
    get_supplier_by_name,
    get_warehouse,
    get_all_warehouses,
)
from backend.disruption_parser import DisruptionEvent


# ============================================================
# Resolution result models
# ============================================================

@dataclass(frozen=True)
class EntityMatch:
    """
    Result of resolving one entity against our database.
    """

    input_value: str
    entity_type: str

    entity_id: Optional[str]
    entity_name: Optional[str]

    status: str
    confidence: float

    reason: str

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedProduct:
    """
    A successfully resolved product.
    """

    product_id: str
    product_name: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedDisruption:
    """
    Fully resolved disruption.

    The original AI-extracted information is preserved, while
    verified database IDs are attached separately.
    """

    event_type: str
    supplier: Optional[EntityMatch]
    products: tuple[ResolvedProduct, ...]
    warehouse: Optional[EntityMatch]
    delay_days: Optional[int]
    affected_shipment_ids: tuple[str, ...]
    unresolved_entities: tuple[EntityMatch, ...]
    requires_human_review: bool

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "supplier": (
                self.supplier.to_dict()
                if self.supplier
                else None
            ),
            "products": [
                product.to_dict()
                for product in self.products
            ],
            "warehouse": (
                self.warehouse.to_dict()
                if self.warehouse
                else None
            ),
            "affected_shipment_ids": list(
                self.affected_shipment_ids
            ),
            "unresolved_entities": [
                entity.to_dict()
                for entity in self.unresolved_entities
            ],
            "requires_human_review": self.requires_human_review,
        }

def normalize_name(value: Optional[str]) -> str:
    """
    Normalize text before deterministic database matching.

    Examples:

        " ABC Components " → "abc components"
        "X-200"            → "x-200"
    """

    if not value:
        return ""

    return " ".join(value.strip().lower().split())


# ============================================================
# Supplier resolution
# ============================================================

def resolve_supplier(
    supplier_name: Optional[str],
) -> EntityMatch:
    """
    Resolve a supplier name against the suppliers table.

    Resolution is deterministic.

    No fuzzy guessing is performed.
    """

    if not supplier_name or not supplier_name.strip():
        return EntityMatch(
            input_value="",
            entity_type="supplier",
            entity_id=None,
            entity_name=None,
            status="missing",
            confidence=0.0,
            reason="Supplier was not provided in the disruption notice.",
        )

    normalized_input = normalize_name(supplier_name)

    # First attempt: exact case-insensitive database match.
    supplier = get_supplier_by_name(supplier_name)

    if supplier:
        return EntityMatch(
            input_value=supplier_name,
            entity_type="supplier",
            entity_id=supplier["supplier_id"],
            entity_name=supplier["name"],
            status="resolved",
            confidence=1.0,
            reason="Exact supplier name matched a database record.",
        )

    # We intentionally DO NOT perform fuzzy matching here.
    #
    # Example:
    #
    # "ABC Component"
    #
    # should NOT automatically become:
    #
    # "ABC Components"
    #
    # because an incorrect supplier mapping could cause
    # incorrect downstream business-impact calculations.

    return EntityMatch(
        input_value=supplier_name,
        entity_type="supplier",
        entity_id=None,
        entity_name=None,
        status="unresolved",
        confidence=0.0,
        reason=(
            f"No supplier with normalized name "
            f"'{normalized_input}' exists in the database."
        ),
    )


# ============================================================
# Product resolution
# ============================================================

def resolve_product(
    product_name: str,
) -> EntityMatch:
    """
    Resolve a product name against the products table.

    Only exact deterministic matching is accepted.
    """

    if not product_name or not product_name.strip():
        return EntityMatch(
            input_value=product_name or "",
            entity_type="product",
            entity_id=None,
            entity_name=None,
            status="missing",
            confidence=0.0,
            reason="Product name was empty.",
        )

    normalized_input = normalize_name(product_name)

    product = get_product_by_name(product_name)

    if product:
        return EntityMatch(
            input_value=product_name,
            entity_type="product",
            entity_id=product["product_id"],
            entity_name=product["name"],
            status="resolved",
            confidence=1.0,
            reason="Exact product name matched a database record.",
        )

    return EntityMatch(
        input_value=product_name,
        entity_type="product",
        entity_id=None,
        entity_name=None,
        status="unresolved",
        confidence=0.0,
        reason=(
            f"No product with normalized name "
            f"'{normalized_input}' exists in the database."
        ),
    )


# ============================================================
# Product resolution with supplier validation
# ============================================================

def resolve_products(
    product_names: list[str],
    supplier_id: Optional[str] = None,
) -> tuple[
    tuple[ResolvedProduct, ...],
    tuple[EntityMatch, ...],
]:
    """
    Resolve all products mentioned in a disruption.

    If a supplier is known, verify that each resolved product
    actually belongs to that supplier.

    This prevents a disruption for Supplier A from accidentally
    being mapped to a similarly named product belonging to
    Supplier B.
    """

    resolved_products: list[ResolvedProduct] = []
    unresolved: list[EntityMatch] = []

    seen_product_ids: set[str] = set()

    for product_name in product_names:

        match = resolve_product(product_name)

        if not match.resolved:
            unresolved.append(match)
            continue

        product = get_product_by_name(product_name)

        if product is None:
            # Defensive check. This should not normally happen
            # because resolve_product already found the record.
            unresolved.append(
                EntityMatch(
                    input_value=product_name,
                    entity_type="product",
                    entity_id=None,
                    entity_name=None,
                    status="unresolved",
                    confidence=0.0,
                    reason="Product disappeared during resolution.",
                )
            )
            continue

        # ----------------------------------------------------
        # Supplier-product consistency check
        # ----------------------------------------------------

        if supplier_id and product["supplier_id"] != supplier_id:

            unresolved.append(
                EntityMatch(
                    input_value=product_name,
                    entity_type="product",
                    entity_id=product["product_id"],
                    entity_name=product["name"],
                    status="conflict",
                    confidence=0.0,
                    reason=(
                        f"Product belongs to supplier "
                        f"{product['supplier_id']}, not the resolved "
                        f"supplier {supplier_id}."
                    ),
                )
            )

            continue

        # Prevent duplicate products from appearing twice.
        if product["product_id"] in seen_product_ids:
            continue

        seen_product_ids.add(product["product_id"])

        resolved_products.append(
            ResolvedProduct(
                product_id=product["product_id"],
                product_name=product["name"],
            )
        )

    return (
        tuple(resolved_products),
        tuple(unresolved),
    )

def resolve_warehouse(
    warehouse_name: str,
) -> EntityMatch:
    if not warehouse_name or not warehouse_name.strip():
        return EntityMatch(
            input_value=warehouse_name or "",
            entity_type="warehouse",
            entity_id=None,
            entity_name=None,
            status="missing",
            confidence=0.0,
            reason="Warehouse name was not provided.",
        )

    normalized_input = normalize_name(warehouse_name)

    for warehouse in get_all_warehouses():
        if normalize_name(warehouse["name"]) == normalized_input:
            return EntityMatch(
                input_value=warehouse_name,
                entity_type="warehouse",
                entity_id=warehouse["warehouse_id"],
                entity_name=warehouse["name"],
                status="resolved",
                confidence=1.0,
                reason="Exact warehouse name matched a database record.",
            )

    return EntityMatch(
        input_value=warehouse_name,
        entity_type="warehouse",
        entity_id=None,
        entity_name=None,
        status="unresolved",
        confidence=0.0,
        reason=(
            f"No warehouse with normalized name "
            f"'{normalized_input}' exists in the database."
        ),
    )


# ============================================================
# Complete disruption resolution
# ============================================================

def resolve_disruption(
    disruption: DisruptionEvent,
) -> ResolvedDisruption:
    """
    Resolve the AI-extracted disruption against our actual
    supply-chain database.

    Important:

    Gemini provides interpretation.

    This function verifies that interpretation against
    deterministic application data.
    """

    # --------------------------------------------------------
    # Resolve supplier
    # --------------------------------------------------------

    resolved_shipments = []
    shipment_entities: list[EntityMatch] = []

    for shipment_id in disruption.affected_shipments:
        shipment = get_shipments(shipment_id)

        if shipment is None:
            shipment_entities.append(
                EntityMatch(
                    input_value=shipment_id,
                    entity_type="shipment",
                    entity_id=None,
                    entity_name=None,
                    status="unresolved",
                    confidence=0.0,
                    reason="No shipment with this exact ID exists in the database.",
                )
            )
            continue

        resolved_shipments.append(shipment)

    # A carrier notice can identify a shipment without naming the supplier.
    # In that case supplier/product/warehouse are derived only from the exact
    # shipment record, never guessed from the carrier name.
    if disruption.supplier_name:
        supplier_match = resolve_supplier(disruption.supplier_name)
    elif resolved_shipments:
        supplier_ids = {shipment["supplier_id"] for shipment in resolved_shipments}
        if len(supplier_ids) == 1:
            supplier = get_supplier(next(iter(supplier_ids)))
            if supplier is not None:
                supplier_match = EntityMatch(
                    input_value=", ".join(shipment["shipment_id"] for shipment in resolved_shipments),
                    entity_type="supplier",
                    entity_id=supplier["supplier_id"],
                    entity_name=supplier["name"],
                    status="resolved",
                    confidence=1.0,
                    reason="Derived from the exact resolved shipment record.",
                )
            else:
                supplier_match = resolve_supplier(None)
        else:
            supplier_match = resolve_supplier(None)
    else:
        supplier_match = resolve_supplier(None)

    # --------------------------------------------------------
    # Resolve products
    # --------------------------------------------------------

    supplier_id = (
        supplier_match.entity_id
        if supplier_match.resolved
        else None
    )

    products, unresolved_products = resolve_products(
        disruption.affected_products,
        supplier_id=supplier_id,
    )

    # Shipment IDs establish affected products even if the carrier notice did
    # not repeat the product name. Explicit products still go through the
    # usual exact resolver above.
    resolved_product_ids = {product.product_id for product in products}
    derived_products: list[ResolvedProduct] = list(products)

    for shipment in resolved_shipments:
        product = get_product(shipment["product_id"])
        if product is None:
            continue

        if product["product_id"] not in resolved_product_ids:
            derived_products.append(
                ResolvedProduct(
                    product_id=product["product_id"],
                    product_name=product["name"],
                )
            )
            resolved_product_ids.add(product["product_id"])

    # An explicit product and an explicit shipment must agree. Do not widen a
    # carrier disruption to unrelated products.
    mentioned_product_ids = {
        product.product_id for product in products
    }
    shipment_product_ids = {
        shipment["product_id"] for shipment in resolved_shipments
    }

    if mentioned_product_ids and shipment_product_ids and not (
        mentioned_product_ids & shipment_product_ids
    ):
        unresolved_products += (
            EntityMatch(
                input_value=", ".join(disruption.affected_products),
                entity_type="product",
                entity_id=None,
                entity_name=None,
                status="conflict",
                confidence=0.0,
                reason="Explicit product does not match the resolved shipment product.",
            ),
        )
    # --------------------------------------------------------
    # Resolve warehouse
    # --------------------------------------------------------

    if disruption.warehouse_name:
        warehouse_match = resolve_warehouse(
            disruption.warehouse_name
        )
    else:
        warehouse_match = None

    # --------------------------------------------------------
    # Collect unresolved entities
    # --------------------------------------------------------

    unresolved_entities: list[EntityMatch] = []

    if supplier_match.status == "unresolved":
        unresolved_entities.append(supplier_match)

    if warehouse_match and not warehouse_match.resolved:
        unresolved_entities.append(warehouse_match)

    unresolved_entities.extend(unresolved_products)
    unresolved_entities.extend(shipment_entities)

    # --------------------------------------------------------
    # Determine whether human review is required
    # --------------------------------------------------------

    requires_human_review = len(unresolved_entities) > 0

    return ResolvedDisruption(
        event_type=disruption.event_type,
        supplier=(
            supplier_match
            if disruption.supplier_name or resolved_shipments
            else None
        ),
        delay_days=disruption.delay_days,
        products=tuple(derived_products),
        warehouse=warehouse_match,
        affected_shipment_ids=tuple(
            shipment["shipment_id"]
            for shipment in resolved_shipments
        ),
        unresolved_entities=tuple(unresolved_entities),
        requires_human_review=requires_human_review,
    )


# ============================================================
# Pretty printing
# ============================================================

def print_resolution(result: ResolvedDisruption) -> None:
    """
    Print a human-readable resolution result.
    """

    print("\nRippleX Entity Resolution")
    print("=" * 50)

    print(f"\nEvent type: {result.event_type}")

    print("\nSupplier:")

    if result.supplier:
        print(
            f"  Input:      {result.supplier.input_value}"
        )
        print(
            f"  Database:   {result.supplier.entity_name}"
        )
        print(
            f"  ID:         {result.supplier.entity_id}"
        )
        print(
            f"  Status:     {result.supplier.status}"
        )
        print(
            f"  Confidence: {result.supplier.confidence}"
        )
    else:
        print("  Not provided.")

    print("\nResolved products:")

    if result.products:
        for product in result.products:
            print(
                f"  ✓ {product.product_name}"
                f" → {product.product_id}"
            )
    else:
        print("  None.")

    print("\nUnresolved / conflicting entities:")

    if result.unresolved_entities:
        for entity in result.unresolved_entities:
            print(
                f"  ⚠ {entity.entity_type}: "
                f"{entity.input_value}"
            )
            print(
                f"    Status: {entity.status}"
            )
            print(
                f"    Reason: {entity.reason}"
            )
    else:
        print("  None.")

    print(
        "\nHuman review required:",
        "YES" if result.requires_human_review else "NO",
    )

