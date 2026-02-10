import sqlite3
import uuid
import os
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tracker.db")

ITEM_TYPES = ("book", "audiobook", "youtube_video", "course")
UNIT_TYPES = ("pages", "hours", "chapters", "videos", "exercises", "questions", "minutes", "files")
STATUSES = ("active", "waitlist", "abandoned")


def format_unit_value(value: float, unit_type: str) -> str:
    """Format a unit value for display as a plain integer."""
    return f"{int(value)}"


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _db(commit=False):
    conn = _get_conn()
    try:
        yield conn
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _db(commit=True) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                total_units REAL NOT NULL CHECK(total_units > 0),
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                units_completed REAL NOT NULL CHECK(units_completed >= 0),
                timestamp TEXT NOT NULL,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'completed'
            );
            CREATE INDEX IF NOT EXISTS idx_checkpoints_item ON checkpoints(item_id);
            CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
            CREATE INDEX IF NOT EXISTS idx_checkpoints_item_status ON checkpoints(item_id, status);
            """
        )

        # Migration: remove old CHECK constraint on unit_type if it blocks new types
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='items'"
        ).fetchone()
        if table_sql and "'minutes'" not in table_sql[0]:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
                CREATE TABLE items_new (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    unit_type TEXT NOT NULL,
                    total_units REAL NOT NULL CHECK(total_units > 0),
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL
                );
                INSERT INTO items_new SELECT * FROM items;
                DROP TABLE items;
                ALTER TABLE items_new RENAME TO items;
                CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
            """)
            conn.execute("PRAGMA foreign_keys=ON")

        # Migration: add status column to checkpoints if missing (for existing DBs)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(checkpoints)").fetchall()]
        if "status" not in cols:
            conn.execute("ALTER TABLE checkpoints ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'")


# ---- Items CRUD ----


def add_item(
    name: str,
    item_type: str,
    unit_type: str,
    total_units: float,
    status: str = "active",
    created_at: str | None = None,
    item_id: str | None = None,
) -> dict:
    if item_type not in ITEM_TYPES:
        raise ValueError(f"Invalid item_type: {item_type}")
    if unit_type not in UNIT_TYPES:
        raise ValueError(f"Invalid unit_type: {unit_type}")
    if status not in STATUSES:
        raise ValueError(f"Invalid status: {status}")

    item_id = item_id or str(uuid.uuid4())
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    with _db(commit=True) as conn:
        conn.execute(
            "INSERT INTO items (id, name, item_type, unit_type, total_units, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (item_id, name, item_type, unit_type, total_units, status, created_at),
        )
    return {
        "id": item_id,
        "name": name,
        "item_type": item_type,
        "unit_type": unit_type,
        "total_units": total_units,
        "status": status,
        "created_at": created_at,
    }


def get_items(status: str | None = None, item_type: str | None = None) -> list[dict]:
    with _db() as conn:
        query = "SELECT * FROM items WHERE 1=1"
        params: list = []
        if status:
            query += " AND status=?"
            params.append(status)
        if item_type:
            query += " AND item_type=?"
            params.append(item_type)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_item(item_id: str) -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None


def update_item_status(item_id: str, status: str):
    with _db(commit=True) as conn:
        conn.execute("UPDATE items SET status=? WHERE id=?", (status, item_id))


def delete_item(item_id: str):
    with _db(commit=True) as conn:
        conn.execute("DELETE FROM items WHERE id=?", (item_id,))


# ---- Checkpoints CRUD ----


def add_checkpoint(
    item_id: str,
    units_completed: float,
    timestamp: str | None = None,
    notes: str | None = None,
    cp_id: str | None = None,
    status: str = "completed",
) -> dict:
    cp_id = cp_id or str(uuid.uuid4())
    timestamp = timestamp or datetime.now(timezone.utc).isoformat()
    with _db(commit=True) as conn:
        conn.execute(
            "INSERT INTO checkpoints (id, item_id, units_completed, timestamp, notes, status) VALUES (?,?,?,?,?,?)",
            (cp_id, item_id, units_completed, timestamp, notes, status),
        )
    return {
        "id": cp_id,
        "item_id": item_id,
        "units_completed": units_completed,
        "timestamp": timestamp,
        "notes": notes,
        "status": status,
    }


def get_checkpoints(item_id: str, status: str | None = None) -> list[dict]:
    with _db() as conn:
        query = "SELECT * FROM checkpoints WHERE item_id=?"
        params: list = [item_id]
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY timestamp ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_all_checkpoints_for_items(item_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch checkpoints for multiple items in one query, grouped by item_id."""
    result: dict[str, list[dict]] = {iid: [] for iid in item_ids}
    if not item_ids:
        return result
    with _db() as conn:
        placeholders = ",".join("?" for _ in item_ids)
        query = f"SELECT * FROM checkpoints WHERE item_id IN ({placeholders}) ORDER BY timestamp ASC"
        rows = conn.execute(query, item_ids).fetchall()
        for r in rows:
            d = dict(r)
            result[d["item_id"]].append(d)
    return result


def update_checkpoint_timestamp(cp_id: str):
    """Set a checkpoint's timestamp to current UTC time without changing other fields."""
    with _db(commit=True) as conn:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE checkpoints SET timestamp=? WHERE id=?", (now, cp_id))


def update_item_total(item_id: str, total_units: float):
    with _db(commit=True) as conn:
        conn.execute(
            "UPDATE items SET total_units=? WHERE id=?",
            (total_units, item_id),
        )


def update_checkpoint(cp_id: str, units_completed: float, timestamp: str, notes: str | None):
    with _db(commit=True) as conn:
        conn.execute(
            "UPDATE checkpoints SET units_completed=?, timestamp=?, notes=? WHERE id=?",
            (units_completed, timestamp, notes, cp_id),
        )


def delete_checkpoint(cp_id: str):
    with _db(commit=True) as conn:
        conn.execute("DELETE FROM checkpoints WHERE id=?", (cp_id,))


# ---- Export / Import ----


def export_all() -> dict:
    with _db() as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM items").fetchall()]
        checkpoints = [dict(r) for r in conn.execute("SELECT * FROM checkpoints").fetchall()]
        return {"items": items, "checkpoints": checkpoints}


def _is_legacy_format(data: dict) -> bool:
    return "books" in data and isinstance(data["books"], list)


def import_all(data: dict):
    """Import data, auto-detecting legacy format."""
    if _is_legacy_format(data):
        from migration import convert_legacy
        data = convert_legacy(data)

    with _db(commit=True) as conn:
        conn.execute("DELETE FROM checkpoints")
        conn.execute("DELETE FROM items")

        item_rows = [
            (
                item["id"],
                item["name"],
                item["item_type"],
                item["unit_type"],
                item["total_units"],
                item.get("status", "active"),
                item["created_at"],
            )
            for item in data.get("items", [])
        ]
        conn.executemany(
            "INSERT INTO items (id, name, item_type, unit_type, total_units, status, created_at) VALUES (?,?,?,?,?,?,?)",
            item_rows,
        )

        cp_rows = [
            (
                cp["id"],
                cp["item_id"],
                cp["units_completed"],
                cp["timestamp"],
                cp.get("notes"),
                cp.get("status", "completed"),
            )
            for cp in data.get("checkpoints", [])
        ]
        conn.executemany(
            "INSERT INTO checkpoints (id, item_id, units_completed, timestamp, notes, status) VALUES (?,?,?,?,?,?)",
            cp_rows,
        )
