from kivy.app import App
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.snackbar import Snackbar
from datetime import datetime, timezone

from db import ITEM_TYPES, UNIT_TYPES, STATUSES, add_item, add_checkpoint


class AddItemScreen(MDScreen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._type_menu = None
        self._unit_menu = None
        self._status_menu = None
        self._selected_date = None

    def on_enter(self):
        """Reset form on screen enter."""
        self.ids.name_field.text = ""
        self.ids.type_btn.text = "book"
        self.ids.unit_btn.text = "pages"
        self.ids.status_btn.text = "active"
        self.ids.total_field.text = ""
        self.ids.date_btn.text = "Now"
        self._selected_date = None

    def show_type_menu(self):
        items = []
        for t in ITEM_TYPES:
            label = t.replace("_", " ").title()
            items.append({
                "text": label,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=t: self._set_type(x),
            })
        self._type_menu = MDDropdownMenu(
            caller=self.ids.type_btn,
            items=items,
            width_mult=3,
        )
        self._type_menu.open()

    def _set_type(self, val):
        self.ids.type_btn.text = val
        if self._type_menu:
            self._type_menu.dismiss()

    def show_unit_menu(self):
        items = []
        for u in UNIT_TYPES:
            items.append({
                "text": u.title(),
                "viewclass": "OneLineListItem",
                "on_release": lambda x=u: self._set_unit(x),
            })
        self._unit_menu = MDDropdownMenu(
            caller=self.ids.unit_btn,
            items=items,
            width_mult=3,
        )
        self._unit_menu.open()

    def _set_unit(self, val):
        self.ids.unit_btn.text = val
        if self._unit_menu:
            self._unit_menu.dismiss()

    def show_status_menu(self):
        items = []
        for s in STATUSES:
            items.append({
                "text": s.title(),
                "viewclass": "OneLineListItem",
                "on_release": lambda x=s: self._set_status(x),
            })
        self._status_menu = MDDropdownMenu(
            caller=self.ids.status_btn,
            items=items,
            width_mult=3,
        )
        self._status_menu.open()

    def _set_status(self, val):
        self.ids.status_btn.text = val
        if self._status_menu:
            self._status_menu.dismiss()

    def pick_date(self):
        picker = MDDatePicker()
        picker.bind(on_save=self._on_date_picked)
        picker.open()

    def _on_date_picked(self, instance, value, date_range):
        self._selected_date = value
        self.ids.date_btn.text = value.strftime("%Y-%m-%d")

    def submit(self):
        name = self.ids.name_field.text.strip()
        if not name:
            Snackbar(text="Name is required").open()
            return

        total_text = self.ids.total_field.text.strip()
        try:
            total = float(total_text)
            if total <= 0:
                raise ValueError
        except (ValueError, TypeError):
            Snackbar(text="Total must be a positive number").open()
            return

        item_type = self.ids.type_btn.text
        unit_type = self.ids.unit_btn.text
        status = self.ids.status_btn.text

        if self._selected_date:
            created_at = datetime(
                self._selected_date.year,
                self._selected_date.month,
                self._selected_date.day,
                tzinfo=timezone.utc,
            ).isoformat()
        else:
            created_at = datetime.now(timezone.utc).isoformat()

        item = add_item(
            name=name,
            item_type=item_type,
            unit_type=unit_type,
            total_units=total,
            status=status,
            created_at=created_at,
        )

        # Add initial checkpoint at 0
        add_checkpoint(
            item_id=item["id"],
            units_completed=0,
            timestamp=created_at,
            notes="Initial",
        )

        Snackbar(text=f"Created: {name}").open()
        App.get_running_app().go_to_list()
