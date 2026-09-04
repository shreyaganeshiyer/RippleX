import sqlite3
from datetime import date, timedelta
import random

DB_PATH = "data/ripplex.db"


def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Suppliers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT,
            reliability REAL
        )
    """)

    # Products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            supplier_id TEXT,
            unit_cost REAL,
            selling_price REAL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        )
    """)

    # Warehouses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warehouses (
            warehouse_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT
        )
    """)

    # Inventory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            warehouse_id TEXT,
            product_id TEXT,
            quantity INTEGER,
            reserved_quantity INTEGER,
            PRIMARY KEY (warehouse_id, product_id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)

    # Shipments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            shipment_id TEXT PRIMARY KEY,
            supplier_id TEXT,
            product_id TEXT,
            quantity INTEGER,
            warehouse_id TEXT,
            expected_date TEXT,
            status TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id)
        )
    """)

    # Orders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT,
            product_id TEXT,
            quantity INTEGER,
            warehouse_id TEXT,
            promised_date TEXT,
            priority TEXT,
            order_value REAL,
            status TEXT,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id)
        )
    """)

    conn.commit()
    conn.close()


def seed_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear old data so we can safely rerun this script
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM shipments")
    cursor.execute("DELETE FROM inventory")
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM suppliers")
    cursor.execute("DELETE FROM warehouses")

    # -------------------------
    # SUPPLIERS
    # -------------------------

    suppliers = [
        ("SUP001", "ABC Components", "Bangalore", 0.94),
        ("SUP002", "Global Parts", "Chennai", 0.89),
        ("SUP003", "Nova Supplies", "Pune", 0.92),
        ("SUP004", "Prime Manufacturing", "Mumbai", 0.87),
        ("SUP005", "Vertex Industries", "Delhi", 0.95),
    ]

    cursor.executemany("""
        INSERT INTO suppliers
        VALUES (?, ?, ?, ?)
    """, suppliers)

    # -------------------------
    # WAREHOUSES
    # -------------------------

    warehouses = [
        ("WH001", "Bangalore Central", "Bangalore"),
        ("WH002", "Chennai Distribution", "Chennai"),
        ("WH003", "Mumbai Distribution", "Mumbai"),
    ]

    cursor.executemany("""
        INSERT INTO warehouses
        VALUES (?, ?, ?)
    """, warehouses)

    # -------------------------
    # PRODUCTS
    # -------------------------

    products = [
        ("P001", "X-200", "SUP001", 500, 850),
        ("P002", "X-300", "SUP001", 700, 1200),
        ("P003", "X-400", "SUP001", 450, 800),

        ("P004", "Y-100", "SUP002", 300, 550),
        ("P005", "Y-200", "SUP002", 600, 1000),
        ("P006", "Y-300", "SUP002", 800, 1400),

        ("P007", "Z-100", "SUP003", 250, 450),
        ("P008", "Z-200", "SUP003", 400, 700),
        ("P009", "Z-300", "SUP003", 900, 1500),

        ("P010", "A-100", "SUP004", 350, 650),
        ("P011", "A-200", "SUP004", 550, 950),
        ("P012", "A-300", "SUP004", 750, 1300),

        ("P013", "B-100", "SUP005", 200, 400),
        ("P014", "B-200", "SUP005", 500, 900),
        ("P015", "B-300", "SUP005", 1000, 1800),
    ]

    cursor.executemany("""
        INSERT INTO products
        VALUES (?, ?, ?, ?, ?)
    """, products)

    # -------------------------
    # INVENTORY
    # -------------------------

    random.seed(42)

    inventory = []

    for warehouse_id, _, _ in warehouses:
        for product_id, _, _, _, _ in products:
            quantity = random.randint(20, 150)
            reserved = random.randint(0, min(15, quantity))

            inventory.append(
                (warehouse_id, product_id, quantity, reserved)
            )

    cursor.executemany("""
        INSERT INTO inventory
        VALUES (?, ?, ?, ?)
    """, inventory)

    # -------------------------
    # SHIPMENTS
    # -------------------------

    today = date.today()

    shipments = [
        ("SH001", "SUP001", "P001", 120, "WH001",
         str(today + timedelta(days=10)), "IN_TRANSIT"),

        ("SH002", "SUP001", "P002", 100, "WH001",
         str(today + timedelta(days=12)), "IN_TRANSIT"),

        ("SH003", "SUP002", "P004", 150, "WH002",
         str(today + timedelta(days=7)), "IN_TRANSIT"),

        ("SH004", "SUP003", "P007", 200, "WH003",
         str(today + timedelta(days=5)), "IN_TRANSIT"),

        ("SH005", "SUP004", "P010", 100, "WH003",
         str(today + timedelta(days=8)), "IN_TRANSIT"),

        ("SH006", "SUP005", "P013", 180, "WH001",
         str(today + timedelta(days=6)), "IN_TRANSIT"),
    ]

    cursor.executemany("""
        INSERT INTO shipments
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, shipments)

    # -------------------------
    # ORDERS
    # -------------------------

    orders = []

    for i in range(1, 101):

        product = random.choice(products)
        product_id = product[0]
        selling_price = product[4]

        warehouse_id = random.choice(["WH001", "WH002", "WH003"])

        quantity = random.randint(2, 15)

        promised_date = today + timedelta(
            days=random.randint(2, 20)
        )

        priority = random.choice(
            ["LOW", "MEDIUM", "HIGH"]
        )

        order_value = quantity * selling_price

        orders.append((
            f"ORD{i:03d}",
            f"Customer {i}",
            product_id,
            quantity,
            warehouse_id,
            str(promised_date),
            priority,
            order_value,
            "PENDING"
        ))

    cursor.executemany("""
        INSERT INTO orders
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, orders)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_database()
    seed_data()

    print("RippleX database created successfully!")