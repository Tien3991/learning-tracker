from kivy.app import App
from kivy.properties import StringProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.pickers import MDDatePicker, MDTimePicker
from kivymd.uix.snackbar import Snackbar
from kivy.metrics import dp
from datetime import datetime, timezone

from db import (
    get_item, get_checkpoints, add_checkpoint, delete_item,
    update_item_status, update_item_total, update_checkpoint,
    update_checkpoint_timestamp, delete_checkpoint, STATUSES,
)
from estimation import compute_estimation, format_speed, format_duration, format_eta
from charts import build_progress_chart
from widgets.checkpoint_row import CheckpointRow

ICON_MAP = {
    "book": "book-open-variant",
    "audiobook": "headphones",
    "youtube_video": "youtube",
    "course": "school",
}


class DetailScreen(MDScreen):
    item_id = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._item = None
        self._checkpoints = []
        self._estimation = {}
        self._status_menu = None
        self._edit_dialog = None
        self._edit_cp_dialog = None
        self._delete_dialog = None
        self._cp_date = None
        self._cp_time = None

    def on_enter(self):
        self._cp_date = None
        self._cp_time = None
        self.ids.cp_date_btn.text = "Date: Now"
        self.ids.cp_time_btn.text = "Time: Now"
        self.ids.cp_value_field.text = ""
        self.ids.cp_notes_field.text = ""
        self.load_data()

    def load_data(self):
        if not self.item_id:
            return

        self._item = get_item(self.item_id)
        if not self._item:
            App.get_running_app().go_to_list()
            return

        self._checkpoints = get_checkpoints(self.item_id)
        completed_cps = [cp for cp in self._checkpoints if cp.get("status", "completed") == "completed"]
        self._estimation = compute_estimation(self._item, self._checkpoints)

        item = self._item
        est = self._estimation

        # Update toolbar
        self.ids.toolbar.title = item["name"]

        # Update header
        self.ids.type_icon.icon = ICON_MAP.get(item["item_type"], "book-open-variant")
        self.ids.item_name_label.text = item["name"]
        self.ids.status_chip.text = item["status"].title()

        # Update progress
        current = est["current"]
        total = item["total_units"]
        pct = est["percent"]
        self.ids.progress_bar.value = pct
        self.ids.progress_text.text = f"{int(current)} / {int(total)} {item['unit_type']} ({pct:.0f}%)"

        # Update stats
        self.ids.speed_label.text = format_speed(est.get("speed"), item["unit_type"])
        self.ids.time_remaining_label.text = format_duration(est.get("hours_remaining"))
        self.ids.eta_label.text = format_eta(est.get("eta"))

        # Update chart
        chart_container = self.ids.chart_container
        chart_container.clear_widgets()
        chart = build_progress_chart(item, completed_cps, est)
        chart_container.add_widget(chart)

        # Update checkpoints list
        cp_list = self.ids.checkpoints_list
        cp_list.clear_widgets()
        for cp in reversed(self._checkpoints):
            row = CheckpointRow(
                cp_data=cp,
                on_refresh=self._refresh_checkpoint,
                on_edit=self._edit_checkpoint,
                on_delete=self._delete_checkpoint,
            )
            cp_list.add_widget(row)

    # ---- Checkpoint add ----

    def _get_checkpoint_timestamp(self):
        """Build timestamp from selected date/time or use now."""
        if self._cp_date or self._cp_time:
            now = datetime.now(timezone.utc)
            d = self._cp_date or now.date()
            t = self._cp_time or now.time()
            dt = datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=timezone.utc)
            return dt.isoformat()
        return datetime.now(timezone.utc).isoformat()

    def add_checkpoint_cumulative(self):
        """Add checkpoint: value is added to current progress."""
        val_text = self.ids.cp_value_field.text.strip()
        if not val_text:
            Snackbar(text="Enter a value").open()
            return
        try:
            val = float(val_text)
        except ValueError:
            Snackbar(text="Invalid number").open()
            return

        current = self._estimation.get("current", 0)
        new_total = current + val
        notes = self.ids.cp_notes_field.text.strip() or None
        timestamp = self._get_checkpoint_timestamp()

        add_checkpoint(
            item_id=self.item_id,
            units_completed=new_total,
            timestamp=timestamp,
            notes=notes,
        )
        self.ids.cp_value_field.text = ""
        self.ids.cp_notes_field.text = ""
        self._cp_date = None
        self._cp_time = None
        self.ids.cp_date_btn.text = "Date: Now"
        self.ids.cp_time_btn.text = "Time: Now"
        self.load_data()

    def add_checkpoint_absolute(self):
        """Add checkpoint: value is the absolute progress."""
        val_text = self.ids.cp_value_field.text.strip()
        if not val_text:
            Snackbar(text="Enter a value").open()
            return
        try:
            val = float(val_text)
        except ValueError:
            Snackbar(text="Invalid number").open()
            return

        notes = self.ids.cp_notes_field.text.strip() or None
        timestamp = self._get_checkpoint_timestamp()

        add_checkpoint(
            item_id=self.item_id,
            units_completed=val,
            timestamp=timestamp,
            notes=notes,
        )
        self.ids.cp_value_field.text = ""
        self.ids.cp_notes_field.text = ""
        self._cp_date = None
        self._cp_time = None
        self.ids.cp_date_btn.text = "Date: Now"
        self.ids.cp_time_btn.text = "Time: Now"
        self.load_data()

    def pick_cp_date(self):
        picker = MDDatePicker()
        picker.bind(on_save=self._on_cp_date_picked)
        picker.open()

    def _on_cp_date_picked(self, instance, value, date_range):
        self._cp_date = value
        self.ids.cp_date_btn.text = f"Date: {value.strftime('%m/%d')}"

    def pick_cp_time(self):
        picker = MDTimePicker()
        picker.bind(time=self._on_cp_time_picked)
        picker.open()

    def _on_cp_time_picked(self, instance, value):
        self._cp_time = value
        self.ids.cp_time_btn.text = f"Time: {value.strftime('%H:%M')}"

    # ---- Status menu ----

    def show_status_menu(self):
        items = []
        for s in STATUSES:
            items.append({
                "text": s.title(),
                "viewclass": "OneLineListItem",
                "on_release": lambda x=s: self._set_status(x),
            })
        self._status_menu = MDDropdownMenu(
            caller=self.ids.status_chip,
            items=items,
            width_mult=3,
        )
        self._status_menu.open()

    def _set_status(self, status):
        update_item_status(self.item_id, status)
        if self._status_menu:
            self._status_menu.dismiss()
        self.load_data()

    # ---- Edit total ----

    def show_edit_total_dialog(self):
        self._edit_total_field = MDTextField(
            hint_text="New total",
            input_filter="float",
            text=str(int(self._item["total_units"])) if self._item else "",
        )
        self._edit_dialog = MDDialog(
            title="Edit Total Units",
            type="custom",
            content_cls=self._edit_total_field,
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda x: self._edit_dialog.dismiss()),
                MDRaisedButton(text="Save", on_release=lambda x: self._save_total()),
            ],
        )
        self._edit_dialog.open()

    def _save_total(self):
        try:
            new_total = float(self._edit_total_field.text.strip())
            if new_total <= 0:
                raise ValueError
        except (ValueError, TypeError):
            Snackbar(text="Must be a positive number").open()
            return
        update_item_total(self.item_id, new_total)
        self._edit_dialog.dismiss()
        self.load_data()

    # ---- Delete item ----

    def confirm_delete(self):
        self._delete_dialog = MDDialog(
            title="Delete Item?",
            text=f"Delete \"{self._item['name']}\" and all its checkpoints?",
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda x: self._delete_dialog.dismiss()),
                MDRaisedButton(text="Delete", on_release=lambda x: self._do_delete()),
            ],
        )
        self._delete_dialog.open()

    def _do_delete(self):
        delete_item(self.item_id)
        self._delete_dialog.dismiss()
        App.get_running_app().go_to_list()

    # ---- Checkpoint actions ----

    def _refresh_checkpoint(self, cp_id):
        update_checkpoint_timestamp(cp_id)
        Snackbar(text="Timestamp updated").open()
        self.load_data()

    def _edit_checkpoint(self, cp_data):
        self._editing_cp = cp_data

        from kivymd.uix.boxlayout import MDBoxLayout
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(150),
        )

        self._edit_cp_value = MDTextField(
            hint_text="Units completed",
            input_filter="float",
            text=str(int(cp_data["units_completed"])),
        )
        content.add_widget(self._edit_cp_value)

        self._edit_cp_notes = MDTextField(
            hint_text="Notes",
            text=cp_data.get("notes", "") or "",
        )
        content.add_widget(self._edit_cp_notes)

        self._edit_cp_dialog = MDDialog(
            title="Edit Checkpoint",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda x: self._edit_cp_dialog.dismiss()),
                MDRaisedButton(text="Save", on_release=lambda x: self._save_edited_cp()),
            ],
        )
        self._edit_cp_dialog.open()

    def _save_edited_cp(self):
        try:
            new_val = float(self._edit_cp_value.text.strip())
        except (ValueError, TypeError):
            Snackbar(text="Invalid number").open()
            return
        notes = self._edit_cp_notes.text.strip() or None
        update_checkpoint(
            self._editing_cp["id"],
            new_val,
            self._editing_cp["timestamp"],
            notes,
        )
        self._edit_cp_dialog.dismiss()
        self.load_data()

    def _delete_checkpoint(self, cp_id):
        delete_checkpoint(cp_id)
        Snackbar(text="Checkpoint deleted").open()
        self.load_data()
