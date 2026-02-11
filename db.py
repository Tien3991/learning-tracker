import uuid
from datetime import datetime, timezone

import streamlit as st
from supabase import create_client, Client

ITEM_TYPES = ("book", "audiobook", "youtube_video", "course")
UNIT_TYPES = ("pages", "hours", "chapters", "videos", "exercises", "questions", "minutes", "files")
STATUSES = ("active", "waitlist", "abandoned")


def format_unit_value(value: float, unit_type: str) -> str:
    """Format a unit value for display as a plain integer."""
    return f"{int(value)}"


def _get_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def init_db():
    """No-op — tables are created via the Supabase SQL Editor."""
    pass


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
    row = {
        "id": item_id,
        "name": name,
        "item_type": item_type,
        "unit_type": unit_type,
        "total_units": total_units,
        "status": status,
        "created_at": created_at,
    }
    _get_client().table("items").insert(row).execute()
    return row


def get_items(status: str | None = None, item_type: str | None = None) -> list[dict]:
    q = _get_client().table("items").select("*")
    if status:
        q = q.eq("status", status)
    if item_type:
        q = q.eq("item_type", item_type)
    q = q.order("created_at", desc=True)
    return q.execute().data


def get_item(item_id: str) -> dict | None:
    resp = _get_client().table("items").select("*").eq("id", item_id).execute()
    return resp.data[0] if resp.data else None


def update_item_status(item_id: str, status: str):
    _get_client().table("items").update({"status": status}).eq("id", item_id).execute()


def delete_item(item_id: str):
    _get_client().table("items").delete().eq("id", item_id).execute()


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
    row = {
        "id": cp_id,
        "item_id": item_id,
        "units_completed": units_completed,
        "timestamp": timestamp,
        "notes": notes,
        "status": status,
    }
    _get_client().table("checkpoints").insert(row).execute()
    return row


def get_checkpoints(item_id: str, status: str | None = None) -> list[dict]:
    q = _get_client().table("checkpoints").select("*").eq("item_id", item_id)
    if status:
        q = q.eq("status", status)
    q = q.order("timestamp", desc=False)
    return q.execute().data


def get_all_checkpoints_for_items(item_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch checkpoints for multiple items in one query, grouped by item_id."""
    result: dict[str, list[dict]] = {iid: [] for iid in item_ids}
    if not item_ids:
        return result
    resp = (
        _get_client()
        .table("checkpoints")
        .select("*")
        .in_("item_id", item_ids)
        .order("timestamp", desc=False)
        .execute()
    )
    for row in resp.data:
        result[row["item_id"]].append(row)
    return result


def update_checkpoint_timestamp(cp_id: str):
    """Set a checkpoint's timestamp to current UTC time without changing other fields."""
    now = datetime.now(timezone.utc).isoformat()
    _get_client().table("checkpoints").update({"timestamp": now}).eq("id", cp_id).execute()


def update_item_total(item_id: str, total_units: float):
    _get_client().table("items").update({"total_units": total_units}).eq("id", item_id).execute()


def update_checkpoint(cp_id: str, units_completed: float, timestamp: str, notes: str | None):
    _get_client().table("checkpoints").update({
        "units_completed": units_completed,
        "timestamp": timestamp,
        "notes": notes,
    }).eq("id", cp_id).execute()


def delete_checkpoint(cp_id: str):
    _get_client().table("checkpoints").delete().eq("id", cp_id).execute()


# ---- Export / Import ----


def export_all() -> dict:
    client = _get_client()
    items = client.table("items").select("*").execute().data
    checkpoints = client.table("checkpoints").select("*").execute().data
    return {"items": items, "checkpoints": checkpoints}


def _is_legacy_format(data: dict) -> bool:
    return "books" in data and isinstance(data["books"], list)


def import_all(data: dict):
    """Import data, auto-detecting legacy format."""
    if _is_legacy_format(data):
        from migration import convert_legacy
        data = convert_legacy(data)

    client = _get_client()

    # Delete all existing data (checkpoints first due to FK constraint)
    client.table("checkpoints").delete().neq("id", "").execute()
    client.table("items").delete().neq("id", "").execute()

    # Insert items
    item_rows = [
        {
            "id": item["id"],
            "name": item["name"],
            "item_type": item["item_type"],
            "unit_type": item["unit_type"],
            "total_units": item["total_units"],
            "status": item.get("status", "active"),
            "created_at": item["created_at"],
        }
        for item in data.get("items", [])
    ]
    if item_rows:
        client.table("items").insert(item_rows).execute()

    # Insert checkpoints
    cp_rows = [
        {
            "id": cp["id"],
            "item_id": cp["item_id"],
            "units_completed": cp["units_completed"],
            "timestamp": cp["timestamp"],
            "notes": cp.get("notes"),
            "status": cp.get("status", "completed"),
        }
        for cp in data.get("checkpoints", [])
    ]
    if cp_rows:
        client.table("checkpoints").insert(cp_rows).execute()
