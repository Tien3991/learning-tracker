from datetime import datetime, timezone
from dateutil.parser import parse as parse_dt


def compute_estimation(item: dict, checkpoints: list[dict]) -> dict:
    """
    Port of computeEstimation() from legacy app.js.
    Returns dict with current progress, speed, hours remaining, ETA.
    Only uses completed checkpoints for computation.
    """
    total = item["total_units"]
    unit = item["unit_type"]

    # Filter to completed checkpoints only
    completed = [cp for cp in checkpoints if cp.get("status", "completed") == "completed"]

    current = completed[-1]["units_completed"] if completed else 0
    remaining = total - current
    percent = (current / total * 100) if total > 0 else 0

    if len(completed) < 2:
        return {
            "current": current,
            "percent": percent,
            "remaining": remaining,
            "speed": None,
            "hours_remaining": None,
            "eta": None,
            "unit_type": unit,
            "t0": None,
            "slope": None,
        }

    t0 = parse_dt(completed[0]["timestamp"])
    now = datetime.now(timezone.utc)
    elapsed_hours = (now - t0).total_seconds() / 3600

    speed = max(current / elapsed_hours if elapsed_hours > 0 else 0.001, 0.001)
    hours_remaining = remaining / speed
    eta = datetime.fromtimestamp(
        now.timestamp() + hours_remaining * 3600, tz=timezone.utc
    )

    return {
        "current": current,
        "percent": percent,
        "remaining": remaining,
        "speed": speed,
        "hours_remaining": hours_remaining,
        "eta": eta,
        "unit_type": unit,
        "t0": t0,
        "slope": speed,
    }


def format_speed(speed: float | None, unit_type: str) -> str:
    if speed is None:
        return "\u2014"
    return f"{speed:.1f} {unit_type}/hr"


def format_duration(hours: float | None) -> str:
    if hours is None or hours > 876000:
        return "~100 years"
    if hours < 0:
        return "\u2014"
    total_minutes = round(hours * 60)
    if total_minutes < 60:
        return f"{total_minutes} min"
    days = int(hours // 24)
    h = int(hours % 24)
    m = round((hours - int(hours)) * 60)
    if days > 0:
        return f"{days}d {h}h"
    return f"{int(hours)}h {m}min"


def format_eta(eta) -> str:
    if eta is None:
        return "~100 years"
    now = datetime.now(timezone.utc)
    diff = (eta - now).total_seconds()
    if diff > 876000 * 3600:
        return "~100 years"
    return eta.strftime("%b %d, %Y %H:%M")
