import sqlite3

DB_NAME = "employees.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            chat_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            city TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_chat_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcast_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER NOT NULL,
            employee_chat_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL,
            sent_message_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcast_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            broadcast_id INTEGER NOT NULL,
            employee_chat_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL,
            response_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            delivered_to_admin INTEGER DEFAULT 0,
            FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id)
        )
        """
    )

    conn.commit()
    conn.close()


def add_employee(chat_id: int, name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT chat_id FROM employees WHERE name = ?", (name,))
    existing = cursor.fetchone()
    if existing and existing[0] != chat_id:
        conn.close()
        return False

    try:
        cursor.execute(
            """
            INSERT INTO employees (chat_id, name)
            VALUES (?, ?)
            ON CONFLICT(chat_id)
            DO UPDATE SET name=excluded.name
            """,
            (chat_id, name),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_employee_by_name(name: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM employees WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_employee_name_by_chat_id(chat_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM employees WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


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


def get_setting(key, default=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def update_employee_city(name, city):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE employees SET city=? WHERE name=?", (city, name))
    conn.commit()
    conn.close()


def get_employees_by_city(city):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT chat_id, name FROM employees WHERE city=?", (city,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_employees_with_city():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT chat_id, name, city FROM employees")
    rows = c.fetchall()
    conn.close()
    return rows


def create_broadcast(admin_chat_id: int, message_text: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO broadcasts (admin_chat_id, message_text) VALUES (?, ?)",
        (admin_chat_id, message_text),
    )
    broadcast_id = c.lastrowid
    conn.commit()
    conn.close()
    return broadcast_id


def add_broadcast_recipient(
    broadcast_id: int,
    employee_chat_id: int,
    employee_name: str,
    sent_message_id: int,
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO broadcast_recipients (
            broadcast_id,
            employee_chat_id,
            employee_name,
            sent_message_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (broadcast_id, employee_chat_id, employee_name, sent_message_id),
    )
    conn.commit()
    conn.close()


def get_broadcast_for_reply(employee_chat_id: int, replied_message_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT broadcast_id, employee_name
        FROM broadcast_recipients
        WHERE employee_chat_id = ? AND sent_message_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (employee_chat_id, replied_message_id),
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return {"broadcast_id": row[0], "employee_name": row[1]}


def save_broadcast_response(
    broadcast_id: int,
    employee_chat_id: int,
    employee_name: str,
    response_text: str,
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO broadcast_responses (
            broadcast_id,
            employee_chat_id,
            employee_name,
            response_text
        )
        VALUES (?, ?, ?, ?)
        """,
        (broadcast_id, employee_chat_id, employee_name, response_text),
    )
    response_id = c.lastrowid
    conn.commit()
    conn.close()
    return response_id


def get_undelivered_responses_for_admin(admin_chat_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT
            r.id,
            r.broadcast_id,
            b.message_text,
            r.employee_name,
            r.response_text,
            r.created_at
        FROM broadcast_responses r
        JOIN broadcasts b ON b.id = r.broadcast_id
        WHERE b.admin_chat_id = ? AND r.delivered_to_admin = 0
        ORDER BY r.broadcast_id ASC, r.created_at ASC, r.id ASC
        """,
        (admin_chat_id,),
    )
    rows = c.fetchall()
    conn.close()

    return [
        {
            "response_id": row[0],
            "broadcast_id": row[1],
            "message_text": row[2],
            "employee_name": row[3],
            "response_text": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def mark_responses_delivered(response_ids: list[int]):
    if not response_ids:
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    placeholders = ",".join("?" for _ in response_ids)
    c.execute(
        f"UPDATE broadcast_responses SET delivered_to_admin = 1 WHERE id IN ({placeholders})",
        response_ids,
    )
    conn.commit()
    conn.close()


def get_broadcasts_for_admin(admin_chat_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        """
        SELECT
            b.id,
            b.message_text,
            b.created_at,
            COUNT(DISTINCT br.id) AS recipients_count,
            COUNT(DISTINCT r.id) AS total_responses,
            COUNT(DISTINCT CASE WHEN r.delivered_to_admin = 0 THEN r.id END) AS new_responses
        FROM broadcasts b
        LEFT JOIN broadcast_recipients br ON br.broadcast_id = b.id
        LEFT JOIN broadcast_responses r ON r.broadcast_id = b.id
        WHERE b.admin_chat_id = ?
        GROUP BY b.id, b.message_text, b.created_at
        ORDER BY b.created_at DESC, b.id DESC
        """,
        (admin_chat_id,),
    )

    rows = c.fetchall()
    conn.close()

    return [
        {
            "broadcast_id": row[0],
            "message_text": row[1],
            "created_at": row[2],
            "recipients_count": row[3] or 0,
            "total_responses": row[4] or 0,
            "new_responses": row[5] or 0,
        }
        for row in rows
    ]


def get_broadcast_details_for_admin(admin_chat_id: int, broadcast_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        """
        SELECT
            b.id,
            b.message_text,
            b.created_at,
            COUNT(DISTINCT br.id) AS recipients_count,
            COUNT(DISTINCT r.id) AS total_responses,
            COUNT(DISTINCT CASE WHEN r.delivered_to_admin = 0 THEN r.id END) AS new_responses
        FROM broadcasts b
        LEFT JOIN broadcast_recipients br ON br.broadcast_id = b.id
        LEFT JOIN broadcast_responses r ON r.broadcast_id = b.id
        WHERE b.admin_chat_id = ? AND b.id = ?
        GROUP BY b.id, b.message_text, b.created_at
        """,
        (admin_chat_id, broadcast_id),
    )

    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "broadcast_id": row[0],
        "message_text": row[1],
        "created_at": row[2],
        "recipients_count": row[3] or 0,
        "total_responses": row[4] or 0,
        "new_responses": row[5] or 0,
    }


def get_broadcast_responses_for_admin(admin_chat_id: int, broadcast_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        """
        SELECT
            r.id,
            r.employee_name,
            r.response_text,
            r.created_at,
            r.delivered_to_admin
        FROM broadcast_responses r
        JOIN broadcasts b ON b.id = r.broadcast_id
        WHERE b.admin_chat_id = ? AND r.broadcast_id = ?
        ORDER BY r.created_at DESC, r.id DESC
        """,
        (admin_chat_id, broadcast_id),
    )

    rows = c.fetchall()
    conn.close()

    return [
        {
            "response_id": row[0],
            "employee_name": row[1],
            "response_text": row[2],
            "created_at": row[3],
            "delivered_to_admin": row[4],
        }
        for row in rows
    ]


def mark_broadcast_responses_delivered(admin_chat_id: int, broadcast_id: int):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        """
        UPDATE broadcast_responses
        SET delivered_to_admin = 1
        WHERE broadcast_id = ?
          AND delivered_to_admin = 0
          AND broadcast_id IN (
              SELECT id FROM broadcasts WHERE id = ? AND admin_chat_id = ?
          )
        """,
        (broadcast_id, broadcast_id, admin_chat_id),
    )

    conn.commit()
    conn.close()


def delete_broadcast_for_admin(admin_chat_id: int, broadcast_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "SELECT id FROM broadcasts WHERE id = ? AND admin_chat_id = ?",
        (broadcast_id, admin_chat_id),
    )
    row = c.fetchone()

    if not row:
        conn.close()
        return False

    c.execute("DELETE FROM broadcast_responses WHERE broadcast_id = ?", (broadcast_id,))
    c.execute("DELETE FROM broadcast_recipients WHERE broadcast_id = ?", (broadcast_id,))
    c.execute(
        "DELETE FROM broadcasts WHERE id = ? AND admin_chat_id = ?",
        (broadcast_id, admin_chat_id),
    )

    conn.commit()
    conn.close()
    return True