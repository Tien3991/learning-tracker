from kivy.app import App
from kivy.properties import StringProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.menu import MDDropdownMenu
from kivy.metrics import dp

from db import get_items, get_all_checkpoints_for_items
from estimation import compute_estimation, format_eta
from widgets.item_card import ItemCard


# Tab widget required by MDTabs
class Tab(MDFloatLayout, MDTabsBase):
    pass


# Status mapping for tabs
TAB_STATUS_MAP = {
    "Active": "active",
    "Waitlist": "waitlist",
    "Abandoned": "abandoned",
}


class ListScreen(MDScreen):
    current_status = StringProperty("active")
    current_type_filter = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._type_menu = None

    def on_enter(self):
        self.refresh_items()

    def on_tab_switch(self, instance_tabs, instance_tab, instance_tab_label, tab_text):
        self.current_status = TAB_STATUS_MAP.get(tab_text, "active")
        self.refresh_items()

    def refresh_items(self):
        item_list = self.ids.item_list
        item_list.clear_widgets()

        status = self.current_status
        type_filter = self.current_type_filter or None
        items = get_items(status=status, item_type=type_filter)

        if not items:
            from kivymd.uix.label import MDLabel
            item_list.add_widget(MDLabel(
                text="No items yet. Tap + to add one!",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(48),
            ))
            return

        item_ids = [it["id"] for it in items]
        all_cps = get_all_checkpoints_for_items(item_ids)

        for item in items:
            cps = all_cps.get(item["id"], [])
            est = compute_estimation(item, cps)

            completed_cps = [cp for cp in cps if cp.get("status", "completed") == "completed"]
            current = completed_cps[-1]["units_completed"] if completed_cps else 0

            progress_text = f"{int(current)} / {int(item['total_units'])} {item['unit_type']}"
            eta_text = format_eta(est.get("eta"))
            pct = est.get("percent", 0)

            card = ItemCard(
                item_id=item["id"],
                item_name=item["name"],
                item_type=item["item_type"],
                progress_pct=pct,
                progress_text=progress_text,
                eta_text=f"ETA: {eta_text}" if est.get("eta") else "",
            )
            card.bind(on_release=lambda c: App.get_running_app().go_to_detail(c.item_id))
            item_list.add_widget(card)

    def show_type_filter(self):
        from db import ITEM_TYPES
        menu_items = [
            {
                "text": "All types",
                "viewclass": "OneLineListItem",
                "on_release": lambda: self._set_type_filter(""),
            },
        ]
        for t in ITEM_TYPES:
            label = t.replace("_", " ").title()
            menu_items.append({
                "text": label,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=t: self._set_type_filter(x),
            })

        self._type_menu = MDDropdownMenu(
            caller=self.ids.tabs,
            items=menu_items,
            width_mult=3,
        )
        self._type_menu.open()

    def _set_type_filter(self, type_val):
        self.current_type_filter = type_val
        if self._type_menu:
            self._type_menu.dismiss()
        self.refresh_items()
