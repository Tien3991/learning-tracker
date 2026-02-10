import json
from datetime import datetime, timezone

import streamlit as st
import streamlit.components.v1 as components

from auth import check_auth
from db import (
    ITEM_TYPES,
    STATUSES,
    UNIT_TYPES,
    add_checkpoint,
    add_item,
    delete_checkpoint,
    delete_item,
    export_all,
    format_unit_value,
    get_all_checkpoints_for_items,
    get_checkpoints,
    get_item,
    get_items,
    import_all,
    init_db,
    update_checkpoint,
    update_checkpoint_timestamp,
    update_item_status,
    update_item_total,
)
from estimation import compute_estimation, format_duration, format_eta, format_speed
from charts import build_progress_chart

# ---- Page config ----
st.set_page_config(page_title="Learning Tracker", page_icon="\U0001F4DA", layout="wide")

# ---- Init DB ----
init_db()

# ---- Auth gate ----
if not check_auth():
    st.stop()

# ---- Type display helpers ----
TYPE_LABELS = {
    "book": "\U0001F4D6 Book",
    "audiobook": "\U0001F3A7 Audiobook",
    "youtube_video": "\u25B6\uFE0F YouTube Video",
    "course": "\U0001F393 Course",
}
TYPE_COLORS = {
    "book": "blue",
    "audiobook": "orange",
    "youtube_video": "red",
    "course": "green",
}
STATUS_LABELS = {"active": "Active", "waitlist": "Waitlist", "abandoned": "Abandoned"}


def _type_badge(item_type: str) -> str:
    return TYPE_LABELS.get(item_type, item_type)


def _local_tz():
    """Return the system's local timezone."""
    return datetime.now().astimezone().tzinfo


def _utc_to_local(dt_str: str) -> datetime:
    """Parse a UTC ISO timestamp and convert to local timezone."""
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_local_tz())


def _local_to_utc(dt: datetime) -> str:
    """Convert a local datetime to UTC ISO string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_local_tz())
    return dt.astimezone(timezone.utc).isoformat()


def _format_local_ts(dt_str: str) -> str:
    """Format a UTC ISO timestamp for display in local timezone."""
    local = _utc_to_local(dt_str)
    return local.strftime("%Y-%m-%d %H:%M")


# ---- Sidebar ----
st.sidebar.title("\U0001F4DA Learning Tracker")

status_filter = st.sidebar.radio(
    "Category",
    options=["active", "waitlist", "abandoned"],
    format_func=lambda s: STATUS_LABELS[s],
    index=0,
)

st.sidebar.markdown("**Filter by type**")
type_filters = []
for t in ITEM_TYPES:
    if st.sidebar.checkbox(TYPE_LABELS[t], value=True, key=f"filter_{t}"):
        type_filters.append(t)

st.sidebar.divider()

# Export
@st.cache_data(ttl=60)
def _cached_export():
    return export_all()

export_data = _cached_export()
st.sidebar.download_button(
    "Export Data",
    data=json.dumps(export_data, indent=2, default=str),
    file_name=f"learning-tracker-{datetime.now().strftime('%Y-%m-%d')}.json",
    mime="application/json",
)

# Import
uploaded = st.sidebar.file_uploader("Import Data", type=["json"], key="import_file")
if uploaded is not None:
    try:
        data = json.loads(uploaded.read())
        import_all(data)
        st.sidebar.success("Data imported!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Import failed: {e}")


# ---- View routing ----
if "view" not in st.session_state:
    st.session_state["view"] = "list"
if "detail_item_id" not in st.session_state:
    st.session_state["detail_item_id"] = None


def go_to_detail(item_id: str):
    st.session_state["view"] = "detail"
    st.session_state["detail_item_id"] = item_id


def go_to_list():
    st.session_state["view"] = "list"
    st.session_state["detail_item_id"] = None


# ---- LIST VIEW ----
if st.session_state["view"] == "list":
    # Add item form
    with st.expander("Add New Item", expanded=False):
        with st.form("add_item_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Name", placeholder="e.g. The Great Gatsby")
                new_type = st.selectbox(
                    "Type",
                    options=ITEM_TYPES,
                    format_func=lambda t: TYPE_LABELS[t],
                )
            with col2:
                new_unit = st.selectbox(
                    "Unit",
                    options=UNIT_TYPES,
                    format_func=lambda u: u.capitalize(),
                )
                new_total = st.number_input("Total", min_value=0.1, step=1.0, value=100.0)

            col3, col4 = st.columns(2)
            with col3:
                new_status = st.selectbox(
                    "Status",
                    options=list(STATUSES),
                    format_func=lambda s: STATUS_LABELS[s],
                )
            with col4:
                new_start = st.date_input("Start Date", value=datetime.now(timezone.utc))

            submitted = st.form_submit_button("Add Item")
            if submitted:
                if not new_name.strip():
                    st.error("Name is required.")
                else:
                    created = datetime.combine(
                        new_start, datetime.now(timezone.utc).time(), tzinfo=timezone.utc
                    ).isoformat()
                    item = add_item(
                        name=new_name.strip(),
                        item_type=new_type,
                        unit_type=new_unit,
                        total_units=float(new_total),
                        status=new_status,
                        created_at=created,
                    )
                    add_checkpoint(item["id"], 0.0, timestamp=created)

                    st.success(f"Added: {new_name.strip()}")
                    st.rerun()

    # Fetch and filter items
    items = get_items(status=status_filter)
    if type_filters:
        items = [i for i in items if i["item_type"] in type_filters]
    else:
        items = []

    if not items:
        st.info("No items found. Add one above or adjust your filters.")
    else:
        # Display as grid (3 columns)
        all_item_cps = get_all_checkpoints_for_items([i["id"] for i in items])
        cols = st.columns(3)
        for idx, item in enumerate(items):
            cps = all_item_cps[item["id"]]
            est = compute_estimation(item, cps)
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{item['name']}**")
                    st.caption(_type_badge(item["item_type"]))
                    progress_val = est["percent"] / 100
                    st.progress(min(progress_val, 1.0))
                    unit = item["unit_type"]
                    st.caption(
                        f"{format_unit_value(est['current'], unit)} / "
                        f"{format_unit_value(item['total_units'], unit)} {unit} "
                        f"({est['percent']:.0f}%)"
                    )
                    if est["eta"]:
                        st.caption(f"ETA: {format_eta(est['eta'])}")
                    else:
                        st.caption("ETA: ~100 years")
                    st.button(
                        "View Details",
                        key=f"detail_{item['id']}",
                        on_click=go_to_detail,
                        args=(item["id"],),
                    )

# ---- DETAIL VIEW ----
elif st.session_state["view"] == "detail":
    item_id = st.session_state["detail_item_id"]
    item = get_item(item_id) if item_id else None

    if not item:
        st.error("Item not found.")
        st.button("Back to List", on_click=go_to_list)
        st.stop()

    components.html(
        """<script>
        setTimeout(() => {
            const main = window.parent.document.querySelector('[data-testid="stMain"]');
            if (main) main.scrollTop = 0;
            window.parent.scrollTo(0, 0);
        }, 100);
        </script>""",
        height=0,
    )
    st.button("\u2190 Back to List", on_click=go_to_list)

    # Header
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title(item["name"])
    with col_h2:
        st.markdown(f":{TYPE_COLORS[item['item_type']]}[{_type_badge(item['item_type'])}]")
        st.markdown(f"**Status:** {STATUS_LABELS[item['status']]}")

    all_cps = get_checkpoints(item_id)
    completed_cps = [cp for cp in all_cps if cp.get("status", "completed") == "completed"]
    est = compute_estimation(item, all_cps)
    unit = item["unit_type"]

    # Progress bar
    progress_val = est["percent"] / 100
    st.progress(min(progress_val, 1.0))

    # Editable total units
    edit_total_key = f"editing_total_{item_id}"
    if edit_total_key not in st.session_state:
        st.session_state[edit_total_key] = False

    if st.session_state[edit_total_key]:
        et_cols = st.columns([2, 1, 1])
        with et_cols[0]:
            new_total = st.number_input(
                f"Total {unit}",
                min_value=0.1,
                step=1.0,
                value=float(item["total_units"]),
                key=f"new_total_{item_id}",
            )
        with et_cols[1]:
            if st.button("Save", key=f"save_total_{item_id}"):
                update_item_total(item_id, new_total)
                st.session_state[edit_total_key] = False
                st.rerun()
        with et_cols[2]:
            if st.button("Cancel", key=f"cancel_total_{item_id}"):
                st.session_state[edit_total_key] = False
                st.rerun()
    else:
        prog_cols = st.columns([5, 1])
        with prog_cols[0]:
            st.caption(
                f"{format_unit_value(est['current'], unit)} / "
                f"{format_unit_value(item['total_units'], unit)} {unit} ({est['percent']:.0f}%)"
            )
        with prog_cols[1]:
            if st.button("Edit", key=f"edit_total_{item_id}"):
                st.session_state[edit_total_key] = True
                st.rerun()

    # Stats
    stat_cols = st.columns(3)
    with stat_cols[0]:
        st.metric("Speed", format_speed(est["speed"], unit))
    with stat_cols[1]:
        st.metric("Time Remaining", format_duration(est["hours_remaining"]))
    with stat_cols[2]:
        st.metric("Estimated Completion", format_eta(est["eta"]))

    # Add checkpoint form
    st.subheader("Add Checkpoint")

    with st.form("add_cp_form", clear_on_submit=True):
        fc = st.columns([2, 3, 2, 3, 2])
        with fc[0]:
            cp_value_str = st.text_input(unit.capitalize(), value="", key="cp_value_input")
        with fc[1]:
            cp_date = st.date_input("Date", value=None, key="cp_date_input")
        with fc[2]:
            cp_time = st.time_input("Time", value=None, key="cp_time_input")
        with fc[3]:
            cp_notes = st.text_input("Notes", placeholder="e.g. Chapter 3", key="cp_notes_input")
        with fc[4]:
            add_clicked = st.form_submit_button("+ Add")
            set_clicked = st.form_submit_button("= Set")

        if add_clicked or set_clicked:
            try:
                cp_val = float(cp_value_str)
            except (ValueError, TypeError):
                st.error("Please enter a valid number.")
                st.stop()

            if add_clicked:
                last_val = completed_cps[-1]["units_completed"] if completed_cps else 0
                final_units = last_val + cp_val
            else:
                final_units = cp_val

            final_units = min(final_units, float(item["total_units"]))

            if cp_date is not None and cp_time is not None:
                local_dt = datetime.combine(cp_date, cp_time, tzinfo=_local_tz())
                ts = _local_to_utc(local_dt)
            else:
                ts = datetime.now(timezone.utc).isoformat()
            add_checkpoint(item_id, final_units, timestamp=ts, notes=cp_notes or None)
            st.success("Checkpoint added!")
            st.rerun()

    # Chart
    st.subheader("Progress Chart")
    fig = build_progress_chart(item, completed_cps, est)
    st.plotly_chart(fig, use_container_width=True)

    # Checkpoints table (completed only)
    st.subheader("Checkpoints")
    if completed_cps:
        for cp in completed_cps:
            edit_cp_key = f"editing_cp_{cp['id']}"
            if edit_cp_key not in st.session_state:
                st.session_state[edit_cp_key] = False

            if st.session_state[edit_cp_key]:
                # Edit mode
                local_dt = _utc_to_local(cp["timestamp"])
                ec_cols = st.columns([2, 2, 2, 3, 1, 1])
                with ec_cols[0]:
                    edit_units = st.number_input(
                        "Units",
                        min_value=0.0,
                        step=1.0,
                        value=float(cp["units_completed"]),
                        key=f"edit_units_{cp['id']}",
                        label_visibility="collapsed",
                    )
                with ec_cols[1]:
                    edit_date = st.date_input(
                        "Date",
                        value=local_dt.date(),
                        key=f"edit_date_{cp['id']}",
                        label_visibility="collapsed",
                    )
                with ec_cols[2]:
                    edit_time = st.time_input(
                        "Time",
                        value=local_dt.time(),
                        key=f"edit_time_{cp['id']}",
                        label_visibility="collapsed",
                    )
                with ec_cols[3]:
                    edit_notes = st.text_input(
                        "Notes",
                        value=cp.get("notes") or "",
                        key=f"edit_notes_{cp['id']}",
                        label_visibility="collapsed",
                    )
                with ec_cols[4]:
                    if st.button("Save", key=f"save_cp_{cp['id']}"):
                        new_local = datetime.combine(
                            edit_date, edit_time, tzinfo=_local_tz()
                        )
                        new_ts = _local_to_utc(new_local)
                        update_checkpoint(
                            cp["id"],
                            edit_units,
                            new_ts,
                            edit_notes or None,
                        )
                        st.session_state[edit_cp_key] = False
                        st.rerun()
                with ec_cols[5]:
                    if st.button("Cancel", key=f"cancel_cp_{cp['id']}"):
                        st.session_state[edit_cp_key] = False
                        st.rerun()
            else:
                # Display mode
                cp_cols = st.columns([2, 3, 3, 1, 1, 1])
                with cp_cols[0]:
                    st.write(f"{format_unit_value(cp['units_completed'], unit)} {unit}")
                with cp_cols[1]:
                    st.write(_format_local_ts(cp["timestamp"]))
                with cp_cols[2]:
                    st.write(cp.get("notes") or "")
                with cp_cols[3]:
                    if st.button("\U0001F504", key=f"refresh_ts_{cp['id']}", help="Set to now"):
                        update_checkpoint_timestamp(cp["id"])
                        st.rerun()
                with cp_cols[4]:
                    if st.button("Edit", key=f"edit_cp_{cp['id']}"):
                        st.session_state[edit_cp_key] = True
                        st.rerun()
                with cp_cols[5]:
                    st.button(
                        "\U0001F5D1",
                        key=f"del_cp_{cp['id']}",
                        on_click=lambda cid=cp["id"]: (delete_checkpoint(cid),),
                        help="Delete checkpoint",
                    )
    else:
        st.info("No checkpoints yet.")

    # Status change & delete
    st.divider()
    action_cols = st.columns([2, 1])
    with action_cols[0]:
        current_idx = list(STATUSES).index(item["status"])
        new_status = st.selectbox(
            "Change Status",
            options=list(STATUSES),
            index=current_idx,
            format_func=lambda s: STATUS_LABELS[s],
            key="status_change",
        )
        if new_status != item["status"]:
            if st.button("Update Status"):
                update_item_status(item_id, new_status)
                st.success(f"Status changed to {STATUS_LABELS[new_status]}")
                st.rerun()
    with action_cols[1]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Delete Item", type="primary"):
            st.session_state["confirm_delete"] = True

        if st.session_state.get("confirm_delete"):
            st.warning("Are you sure? This cannot be undone.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, delete"):
                    delete_item(item_id)
                    st.session_state["confirm_delete"] = False
                    go_to_list()
                    st.rerun()
            with c2:
                if st.button("Cancel"):
                    st.session_state["confirm_delete"] = False
                    st.rerun()
