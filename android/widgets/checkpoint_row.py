from kivy.properties import StringProperty, NumericProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDIconButton
from kivy.metrics import dp
from dateutil.parser import parse as parse_dt


def _utc_to_local_str(timestamp_str):
    """Convert UTC ISO timestamp string to local time display."""
    try:
        dt = parse_dt(timestamp_str)
        local_dt = dt.astimezone()
        return local_dt.strftime("%b %d, %H:%M")
    except Exception:
        return timestamp_str[:16] if timestamp_str else ""


class CheckpointRow(MDBoxLayout):
    cp_id = StringProperty("")
    units_text = StringProperty("")
    timestamp_text = StringProperty("")
    notes_text = StringProperty("")

    def __init__(self, cp_data=None, on_refresh=None, on_edit=None, on_delete=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(48)
        self.spacing = dp(4)
        self.padding = (dp(8), 0)

        self._cp_data = cp_data or {}
        self._on_refresh = on_refresh
        self._on_edit = on_edit
        self._on_delete = on_delete

        if cp_data:
            self.cp_id = cp_data.get("id", "")
            self.units_text = str(int(cp_data.get("units_completed", 0)))
            self.timestamp_text = _utc_to_local_str(cp_data.get("timestamp", ""))
            self.notes_text = cp_data.get("notes", "") or ""

        # Units
        self.add_widget(MDLabel(
            text=self.units_text,
            font_style="Body2",
            size_hint_x=0.15,
            bold=True,
        ))

        # Timestamp
        self.add_widget(MDLabel(
            text=self.timestamp_text,
            font_style="Caption",
            size_hint_x=0.3,
        ))

        # Notes
        self.add_widget(MDLabel(
            text=self.notes_text,
            font_style="Caption",
            size_hint_x=0.25,
            shorten=True,
            shorten_from="right",
            theme_text_color="Secondary",
        ))

        # Action buttons
        btn_box = MDBoxLayout(
            orientation="horizontal",
            size_hint_x=0.3,
            spacing=0,
        )

        refresh_btn = MDIconButton(
            icon="refresh",
            on_release=lambda x: self._do_refresh(),
        )
        btn_box.add_widget(refresh_btn)

        edit_btn = MDIconButton(
            icon="pencil",
            on_release=lambda x: self._do_edit(),
        )
        btn_box.add_widget(edit_btn)

        delete_btn = MDIconButton(
            icon="delete",
            on_release=lambda x: self._do_delete(),
        )
        btn_box.add_widget(delete_btn)

        self.add_widget(btn_box)

    def _do_refresh(self):
        if self._on_refresh:
            self._on_refresh(self.cp_id)

    def _do_edit(self):
        if self._on_edit:
            self._on_edit(self._cp_data)

    def _do_delete(self):
        if self._on_delete:
            self._on_delete(self.cp_id)
