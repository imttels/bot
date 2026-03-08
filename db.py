import sqlite3

DB_NAME = "employees.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        chat_id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def add_employee(chat_id: int, name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT chat_id FROM employees WHERE name = ?",
        (name,)
    )
    existing = cursor.fetchone()

    if existing and existing[0] != chat_id:
        conn.close()
        return False

    try:
        cursor.execute("""
        INSERT INTO employees (chat_id, name)
        VALUES (?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET name=excluded.name
        """, (chat_id, name))

        conn.commit()
        conn.close()
        return True

    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_employee_by_name(name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT chat_id FROM employees WHERE name = ?
    """, (name,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return None

def get_all_employees() -> list[tuple[int, str]]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, name FROM employees")
    employees = cursor.fetchall()
    conn.close()
    return employees

def remove_employee(name: str, admin_chat_ids: list[int] | None = None) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT chat_id FROM employees WHERE name = ?", (name,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return False

    employee_chat_id = result[0]

    if admin_chat_ids and employee_chat_id in admin_chat_ids:
        conn.close()
        return False 

    cursor.execute("DELETE FROM employees WHERE name = ?", (name,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted