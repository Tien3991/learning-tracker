# Learning Tracker — Web App Feature List

## Overview

A Streamlit-based web application for tracking learning progress across books, audiobooks, YouTube videos, and courses. Uses SQLite for persistent storage, Plotly for interactive charts, and provides full CRUD operations on items and checkpoints with progress estimation.

---

## 1. Authentication

- **Password gate**: Optional password protection via `TRACKER_PASSWORD` in Streamlit secrets or environment variable
- **Session persistence**: Once authenticated, the session remains active until the browser tab is closed
- **Timing-safe comparison**: Uses `hmac.compare_digest()` to prevent timing attacks on password verification
- **Bypass when unconfigured**: If no password is set, the app is freely accessible (no login screen shown)

**Files**: `auth.py`

---

## 2. Item Types

Four supported learning content types, each with a distinct emoji and color:

| Type | Label | Color | Icon |
|------|-------|-------|------|
| `book` | Book | Blue | `📖` |
| `audiobook` | Audiobook | Orange | `🎧` |
| `youtube_video` | YouTube Video | Red | `▶️` |
| `course` | Course | Green | `🎓` |

---

## 3. Unit Types

Six supported measurement units for tracking progress:

`pages`, `chapters`, `videos`, `exercises`, `questions`, `minutes`

Any unit type can be paired with any item type (e.g., a course measured in "exercises", an audiobook measured in "minutes").

---

## 4. Item Statuses

Three status categories used to organize items:

| Status | Label | Description |
|--------|-------|-------------|
| `active` | Active | Currently being worked on |
| `waitlist` | Waitlist | Planned for later |
| `abandoned` | Abandoned | No longer pursuing |

---

## 5. Sidebar Navigation & Filters

### 5.1 Status Filter
- Radio button group with options: **Active**, **Waitlist**, **Abandoned**
- Defaults to "Active" on page load
- Filters the main item grid immediately on selection

### 5.2 Type Filter
- Checkbox per item type (Book, Audiobook, YouTube Video, Course)
- All checked by default
- Multiple types can be selected simultaneously
- Unchecking all types shows no items (empty state message)

### 5.3 Data Export
- **Download button** labeled "Export Data"
- Exports all items and checkpoints as a single JSON file
- Filename format: `learning-tracker-YYYY-MM-DD.json`
- Cached for 60 seconds (`@st.cache_data(ttl=60)`) to avoid redundant DB queries
- MIME type: `application/json`

### 5.4 Data Import
- **File uploader** accepting `.json` files
- Supports two formats:
  - **Current format**: `{ "items": [...], "checkpoints": [...] }`
  - **Legacy format**: `{ "books": [{ "id", "name", "totalPages", "checkpoints": [...] }] }` — auto-detected and converted via `migration.py`
- On import: **replaces all existing data** (deletes all items and checkpoints first)
- Shows success/error message in sidebar
- Auto-refreshes page after successful import

**Files**: `app.py` (lines 106–128), `db.py` (`export_all`, `import_all`), `migration.py`

---

## 6. List View (Main Screen)

### 6.1 Add New Item Form
- Collapsible expander labeled "Add New Item" (collapsed by default)
- Form fields (in a 2-column layout):
  - **Name** (text input, required) — placeholder: "e.g. The Great Gatsby"
  - **Type** (selectbox) — dropdown with emoji-labeled types
  - **Unit** (selectbox) — dropdown with capitalized unit names
  - **Total** (number input) — minimum 0.1, step 1.0, default 100.0
  - **Status** (selectbox) — defaults to "Active"
  - **Start Date** (date input) — defaults to today
- On submit:
  - Validates name is not empty
  - Creates item with `created_at` set to the selected date + current time (UTC)
  - Automatically creates an initial checkpoint at 0 units with the same timestamp
  - Shows success message and refreshes the page

### 6.2 Item Grid
- **3-column responsive grid** layout
- Each item displayed as a bordered container card showing:
  - **Name** (bold text)
  - **Type badge** (emoji + label, as caption)
  - **Progress bar** (0–100%, Streamlit native progress widget)
  - **Progress text**: `{current} / {total} {unit} ({percent}%)`
  - **ETA**: Estimated completion date, or "~100 years" if insufficient data
  - **"View Details" button** — navigates to detail view
- Items sorted by `created_at DESC` (newest first)
- Empty state: "No items found. Add one above or adjust your filters."

### 6.3 Batch Checkpoint Loading
- All checkpoints for visible items are fetched in a **single SQL query** using `IN (...)` clause
- Grouped by `item_id` in Python for efficient per-item computation
- Avoids N+1 query problem

**Files**: `app.py` (lines 149–237), `db.py` (`get_items`, `get_all_checkpoints_for_items`)

---

## 7. Detail View

### 7.1 Navigation
- **"← Back to List" button** at top
- Auto-scrolls to top of page on entry (via injected JavaScript `scrollTo(0, 0)`)
- Uses Streamlit `session_state` for view routing (`view` and `detail_item_id` keys)

### 7.2 Header
- **Item name** as page title (large, left-aligned)
- **Type badge** with color: e.g., `:blue[📖 Book]`
- **Status label**: e.g., "Status: Active"

### 7.3 Progress Section
- **Progress bar** (Streamlit native, capped at 100%)
- **Progress text**: `{current} / {total} {unit} ({percent}%)`
- **Editable total units**:
  - "Edit" button toggles inline edit mode
  - Number input (min 0.1, step 1.0) pre-filled with current total
  - "Save" and "Cancel" buttons
  - On save: updates DB and refreshes

### 7.4 Statistics Row
Three Streamlit metric widgets in a row:

| Metric | Computation | Display Format |
|--------|-------------|----------------|
| **Speed** | `current_units / elapsed_hours` (since first checkpoint) | `{value} {unit}/hr` or "—" if < 2 checkpoints |
| **Time Remaining** | `remaining_units / speed` | `{d}d {h}h` or `{h}h {m}min` or `{m} min` or "~100 years" |
| **Estimated Completion** | `now + hours_remaining` | `Mon DD, YYYY HH:MM` or "~100 years" |

- Speed calculation uses a minimum floor of 0.001 to avoid division by zero
- Only completed checkpoints (status = "completed") are used for estimation
- Requires at least 2 checkpoints for any estimation; otherwise shows "—" / "~100 years"

**Files**: `estimation.py`

### 7.5 Add Checkpoint Form
- Inline form with 5 columns:
  - **Value** (text input) — numeric value to add or set
  - **Date** (date input) — optional, defaults to `None`
  - **Time** (time input) — optional, defaults to `None`
  - **Notes** (text input) — optional, placeholder: "e.g. Chapter 3"
  - **Two submit buttons**:
    - **"+ Add"** (cumulative mode): Adds the entered value to the current progress. E.g., if current is 50 and you enter 10, checkpoint is recorded at 60.
    - **"= Set"** (absolute mode): Sets progress to the exact entered value. E.g., entering 60 records a checkpoint at 60 regardless of current progress.
- **Timestamp handling**:
  - If both date and time are selected: combines them as local timezone, converts to UTC for storage
  - If either is `None`: uses `datetime.now(timezone.utc)` (current time)
- **Value capping**: The final units value is capped at the item's `total_units` (cannot exceed 100%)
- Shows success message and refreshes on submit

### 7.6 Progress Chart
- **Interactive Plotly scatter chart** with:
  - **Blue solid line with markers**: Actual progress over time (completed checkpoints only)
  - **Red dashed line**: Linear projection from first checkpoint (0 units) to total units based on computed speed/slope
  - **Checkpoint notes** displayed as text labels above each data point
  - **Hover mode**: "x unified" — shows all values at the hovered timestamp
- Chart configuration:
  - X-axis: Time (datetime axis with real timestamps)
  - Y-axis: Units (range fixed 0 to total_units)
  - Height: 400px
  - Horizontal legend at top-right
  - Responsive width (fills container)
- Empty state: Shows "No checkpoints yet" as chart title with empty axes

**Files**: `charts.py`

### 7.7 Checkpoints List
- Displays all completed checkpoints in chronological order
- Each checkpoint row shows (in 6 columns):
  - **Units completed** with unit label (e.g., "120 pages")
  - **Timestamp** in local timezone (format: `YYYY-MM-DD HH:MM`)
  - **Notes** (or empty)
  - **🔄 Refresh button**: Updates the checkpoint's timestamp to current UTC time (preserves all other fields)
  - **Edit button**: Toggles inline edit mode for that row
  - **🗑 Delete button**: Immediately deletes the checkpoint (no confirmation)

### 7.8 Checkpoint Inline Editing
- Triggered by the "Edit" button on any checkpoint row
- Replaces the display row with editable fields:
  - **Units** (number input, pre-filled)
  - **Date** (date input, pre-filled from current timestamp, local timezone)
  - **Time** (time input, pre-filled from current timestamp, local timezone)
  - **Notes** (text input, pre-filled)
  - **Save** and **Cancel** buttons
- On save: Updates units, timestamp (converted local → UTC), and notes in DB

### 7.9 Status Change
- **Selectbox** with all three statuses, pre-selected to current status
- **"Update Status" button** appears only when a different status is selected
- On update: Changes status in DB, shows success message, refreshes

### 7.10 Delete Item
- **"Delete Item" button** (primary/red style)
- **Two-step confirmation**:
  1. First click: Shows warning "Are you sure? This cannot be undone."
  2. Two buttons appear: "Yes, delete" and "Cancel"
- On confirm: Deletes item and all associated checkpoints (CASCADE), navigates back to list view
- Confirmation state tracked via `session_state["confirm_delete"]`

**Files**: `app.py` (lines 240–490), `db.py`

---

## 8. Database

### 8.1 Storage
- **SQLite** with WAL journal mode for better concurrent read performance
- Database file: `data/tracker.db` (relative to project root)
- Foreign keys enabled (`PRAGMA foreign_keys=ON`)
- Connection per-operation pattern (no connection pooling)

### 8.2 Schema

**`items` table**:
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | TEXT | PRIMARY KEY (UUID v4) |
| `name` | TEXT | NOT NULL |
| `item_type` | TEXT | NOT NULL |
| `unit_type` | TEXT | NOT NULL |
| `total_units` | REAL | NOT NULL, CHECK > 0 |
| `status` | TEXT | NOT NULL, DEFAULT 'active' |
| `created_at` | TEXT | NOT NULL (ISO 8601 UTC) |

**`checkpoints` table**:
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | TEXT | PRIMARY KEY (UUID v4) |
| `item_id` | TEXT | NOT NULL, FOREIGN KEY → items(id) ON DELETE CASCADE |
| `units_completed` | REAL | NOT NULL, CHECK >= 0 |
| `timestamp` | TEXT | NOT NULL (ISO 8601 UTC) |
| `notes` | TEXT | nullable |
| `status` | TEXT | NOT NULL, DEFAULT 'completed' |

**Indexes**:
- `idx_checkpoints_item` on `checkpoints(item_id)`
- `idx_items_status` on `items(status)`
- `idx_checkpoints_item_status` on `checkpoints(item_id, status)`

### 8.3 Migrations (Auto-applied on Init)
1. **Unit type constraint removal**: If the `items` table has a CHECK constraint that doesn't include 'minutes', the table is recreated without the constraint (allows new unit types to be added without schema changes)
2. **Checkpoint status column**: If `checkpoints` table is missing the `status` column, adds it with default 'completed'

### 8.4 CRUD Operations
- `add_item()` — Validates item_type, unit_type, status against allowed values
- `get_items(status, item_type)` — Filtered query with optional status and type
- `get_item(item_id)` — Single item lookup
- `update_item_status(item_id, status)` — Status change only
- `update_item_total(item_id, total_units)` — Total units change only
- `delete_item(item_id)` — Cascade-deletes all checkpoints
- `add_checkpoint()` — Accepts optional timestamp, notes, cp_id, status
- `get_checkpoints(item_id, status)` — Ordered by timestamp ASC
- `get_all_checkpoints_for_items(item_ids)` — Batch fetch, grouped by item_id
- `update_checkpoint(cp_id, units, timestamp, notes)` — Full checkpoint update
- `update_checkpoint_timestamp(cp_id)` — Sets timestamp to now (UTC)
- `delete_checkpoint(cp_id)` — Single checkpoint removal

**Files**: `db.py`

---

## 9. Progress Estimation Algorithm

- **Input**: Item metadata + list of checkpoints
- **Filters**: Only checkpoints with `status == "completed"` are used
- **Current progress**: Taken from the last completed checkpoint's `units_completed`
- **Speed calculation**: `current_units / elapsed_hours` where elapsed is from first checkpoint to now
- **Minimum speed floor**: 0.001 units/hour (prevents division by zero and infinite ETAs)
- **Hours remaining**: `(total - current) / speed`
- **ETA**: `now + hours_remaining` as a UTC datetime
- **Slope**: Same as speed (used for chart projection line)
- **Edge cases**:
  - 0 checkpoints: current = 0, all estimates = None
  - 1 checkpoint: current from that checkpoint, all estimates = None
  - 2+ checkpoints: Full estimation available

**Files**: `estimation.py`

---

## 10. Timezone Handling

- **Storage**: All timestamps stored as **UTC ISO 8601** strings in the database
- **Display**: Converted to **local timezone** using `datetime.now().astimezone().tzinfo`
- **Input**: User-selected dates/times treated as local timezone, converted to UTC before storage
- **Fallback**: If no date/time selected in checkpoint form, uses `datetime.now(timezone.utc)`
- **Format**: Displayed as `YYYY-MM-DD HH:MM` in local time

---

## 11. Legacy Data Migration

- Auto-detects legacy format by checking for `"books"` key in imported JSON
- Converts legacy book-only format to the current multi-type format:
  - Each book → item with `item_type="book"`, `unit_type="pages"`
  - Each book checkpoint `page` field → `units_completed`
  - New UUIDs generated for all items and checkpoints
- Transparent to user — import button handles both formats automatically

**Files**: `migration.py`

---

## 12. Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Frontend | Streamlit | latest |
| Charts | Plotly | latest |
| Database | SQLite3 | built-in |
| Date parsing | python-dateutil | latest |
| Language | Python | 3.11+ |

**Files**: `requirements.txt`

---

## 13. UI/UX Details

- **Page config**: Title "Learning Tracker", icon 📚, wide layout
- **Responsive grid**: 3-column card layout on list view
- **Auto-scroll**: Detail view scrolls to top via injected JavaScript
- **Form clear**: Add item and add checkpoint forms clear on submit (`clear_on_submit=True`)
- **Inline editing**: Checkpoints and total units use toggle-based inline edit (no modal dialogs)
- **Color-coded types**: Each item type has a distinct color for visual scanning
- **Empty states**: Informative messages when no items or checkpoints exist
- **Session state routing**: SPA-like navigation between list and detail views without page reload
