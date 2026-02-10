import uuid


def convert_legacy(data: dict) -> dict:
    """
    Convert legacy reading tracker format:
      { books: [{ id, name, totalPages, createdAt, checkpoints: [{ id, page, timestamp, notes }] }] }
    to new format:
      { items: [...], checkpoints: [...] }
    """
    items = []
    checkpoints = []

    for book in data.get("books", []):
        item_id = str(uuid.uuid4())
        items.append(
            {
                "id": item_id,
                "name": book["name"],
                "item_type": "book",
                "unit_type": "pages",
                "total_units": float(book["totalPages"]),
                "status": "active",
                "created_at": book.get("createdAt", ""),
            }
        )

        for cp in book.get("checkpoints", []):
            checkpoints.append(
                {
                    "id": str(uuid.uuid4()),
                    "item_id": item_id,
                    "units_completed": float(cp.get("page", 0)),
                    "timestamp": cp.get("timestamp", ""),
                    "notes": cp.get("notes"),
                }
            )

    return {"items": items, "checkpoints": checkpoints}
