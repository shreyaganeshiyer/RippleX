import sqlite3
from pathlib import Path


# Path to our SQLite database
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ripplex.db"


def get_connection():
    """
    Create and return a connection to the RippleX database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_db(sql, params=()):
    """
    Execute a SELECT query and return all rows as dictionaries.
    """
    conn = get_connection()

    try:
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_supplier(supplier_id):
    """
    Get a supplier by ID.
    """
    rows = query_db(
        """
        SELECT *
        FROM suppliers
        WHERE supplier_id = ?
        """,
        (supplier_id,)
    )

    return rows[0] if rows else None


def get_supplier_by_name(name):
    """
    Find a supplier by normalized name.
    """
    rows = query_db(
        """
        SELECT *
        FROM suppliers
        WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
        """,
        (name,)
    )

    return rows[0] if rows else None


def get_product(product_id):
    """
    Get a product by ID.
    """
    rows = query_db(
        """
        SELECT *
        FROM products
        WHERE product_id = ?
        """,
        (product_id,)
    )

    return rows[0] if rows else None


def get_product_by_name(name):
    """
    Find a product by normalized name.
    """
    rows = query_db(
        """
        SELECT *
        FROM products
        WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
        """,
        (name,)
    )

    return rows[0] if rows else None


def get_inventory(product_id):
    """
    Get inventory information for a product
    across all warehouses.
    """
    return query_db(
        """
        SELECT
            i.warehouse_id,
            w.name AS warehouse_name,
            w.location,
            i.product_id,
            p.name AS product_name,
            i.quantity,
            i.reserved_quantity,
            (i.quantity - i.reserved_quantity) AS available_quantity
        FROM inventory i
        JOIN warehouses w
            ON i.warehouse_id = w.warehouse_id
        JOIN products p
            ON i.product_id = p.product_id
        WHERE i.product_id = ?
        """,
        (product_id,)
    )


def get_shipments(supplier_id=None, product_id=None):
    """
    Get shipments, optionally filtered by supplier or product.
    """
    sql = """
        SELECT
            s.shipment_id,
            s.supplier_id,
            sup.name AS supplier_name,
            s.product_id,
            p.name AS product_name,
            s.quantity,
            s.warehouse_id,
            w.name AS warehouse_name,
            w.location,
            s.expected_date,
            s.status
        FROM shipments s
        JOIN suppliers sup
            ON s.supplier_id = sup.supplier_id
        JOIN products p
            ON s.product_id = p.product_id
        JOIN warehouses w
            ON s.warehouse_id = w.warehouse_id
        WHERE 1 = 1
    """

    params = []

    if supplier_id:
        sql += " AND s.supplier_id = ?"
        params.append(supplier_id)

    if product_id:
        sql += " AND s.product_id = ?"
        params.append(product_id)

    sql += " ORDER BY s.expected_date"

    return query_db(sql, tuple(params))


def get_orders(product_id=None, warehouse_id=None):
    """
    Get pending orders, optionally filtered by product
    or warehouse.
    """
    sql = """
        SELECT
            o.order_id,
            o.customer_name,
            o.product_id,
            p.name AS product_name,
            o.quantity,
            o.warehouse_id,
            w.name AS warehouse_name,
            w.location,
            o.promised_date,
            o.priority,
            o.order_value,
            o.status
        FROM orders o
        JOIN products p
            ON o.product_id = p.product_id
        JOIN warehouses w
            ON o.warehouse_id = w.warehouse_id
        WHERE o.status = 'PENDING'
    """

    params = []

    if product_id:
        sql += " AND o.product_id = ?"
        params.append(product_id)

    if warehouse_id:
        sql += " AND o.warehouse_id = ?"
        params.append(warehouse_id)

    sql += " ORDER BY o.promised_date"

    return query_db(sql, tuple(params))


def get_warehouse(warehouse_id):
    """
    Get a warehouse by ID.
    """
    rows = query_db(
        """
        SELECT *
        FROM warehouses
        WHERE warehouse_id = ?
        """,
        (warehouse_id,)
    )

    return rows[0] if rows else None


def get_all_suppliers():
    """
    Return all suppliers.
    """
    return query_db(
        """
        SELECT *
        FROM suppliers
        ORDER BY name
        """
    )


def get_all_products():
    """
    Return all products.
    """
    return query_db(
        """
        SELECT
            p.*,
            s.name AS supplier_name
        FROM products p
        JOIN suppliers s
            ON p.supplier_id = s.supplier_id
        ORDER BY p.name
        """
    )


def get_all_warehouses():
    """
    Return all warehouses.
    """
    return query_db(
        """
        SELECT *
        FROM warehouses
        ORDER BY name
        """
    )


def get_database_summary():
    """
    Return basic counts from the database.
    Useful for testing and later for the dashboard.
    """
    tables = [
        "suppliers",
        "products",
        "warehouses",
        "inventory",
        "shipments",
        "orders"
    ]

    summary = {}

    conn = get_connection()

    try:
        for table in tables:
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            )
            summary[table] = cursor.fetchone()[0]

    finally:
        conn.close()

    return summary


# ---------------------------------------------------------
# Simple test when running this file directly
# ---------------------------------------------------------

if __name__ == "__main__":

    print("\nRippleX Database Test")
    print("=" * 40)

    print("\nDatabase summary:")
    print(get_database_summary())

    print("\nSupplier SUP001:")
    print(get_supplier("SUP001"))

    print("\nProduct P001:")
    print(get_product("P001"))

    print("\nInventory for P001:")
    for row in get_inventory("P001"):
        print(row)

    print("\nShipments from SUP001:")
    for row in get_shipments(supplier_id="SUP001"):
        print(row)

    print("\nPending orders for P001:")
    for row in get_orders(product_id="P001"):
        print(row)