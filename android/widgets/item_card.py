from kivy.properties import StringProperty, NumericProperty
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivy.metrics import dp

ICON_MAP = {
    "book": "book-open-variant",
    "audiobook": "headphones",
    "youtube_video": "youtube",
    "course": "school",
}


class ItemCard(MDCard):
    item_id = StringProperty("")
    item_name = StringProperty("")
    item_type = StringProperty("")
    progress_pct = NumericProperty(0)
    progress_text = StringProperty("")
    eta_text = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(120)
        self.padding = dp(12)
        self.spacing = dp(6)
        self.md_bg_color = (1, 1, 1, 1)
        self.radius = [dp(8)]
        self.elevation = 1
        self.ripple_behavior = True

        # Top row: icon + name + type
        top_row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=dp(8),
        )

        from kivymd.uix.label import MDIcon
        icon = MDIcon(
            icon=ICON_MAP.get(self.item_type, "book-open-variant"),
            theme_text_color="Primary",
        )
        self._icon = icon
        top_row.add_widget(icon)

        name_label = MDLabel(
            text=self.item_name,
            font_style="Subtitle1",
            size_hint_x=0.7,
            shorten=True,
            shorten_from="right",
        )
        self._name_label = name_label
        top_row.add_widget(name_label)

        type_label = MDLabel(
            text=self.item_type.replace("_", " ").title(),
            font_style="Caption",
            size_hint_x=0.3,
            halign="right",
            theme_text_color="Secondary",
        )
        self._type_label = type_label
        top_row.add_widget(type_label)

        self.add_widget(top_row)

        # Progress bar
        self._progress_bar = MDProgressBar(
            value=self.progress_pct,
            size_hint_y=None,
            height=dp(4),
        )
        self.add_widget(self._progress_bar)

        # Bottom row: progress text + ETA
        bottom_row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(24),
        )

        progress_lbl = MDLabel(
            text=self.progress_text,
            font_style="Body2",
            size_hint_x=0.5,
        )
        self._progress_label = progress_lbl
        bottom_row.add_widget(progress_lbl)

        eta_lbl = MDLabel(
            text=self.eta_text,
            font_style="Caption",
            size_hint_x=0.5,
            halign="right",
            theme_text_color="Secondary",
        )
        self._eta_label = eta_lbl
        bottom_row.add_widget(eta_lbl)

        self.add_widget(bottom_row)

        # Bind properties to update widgets
        self.bind(item_name=self._update_name)
        self.bind(item_type=self._update_type)
        self.bind(progress_pct=self._update_progress)
        self.bind(progress_text=self._update_progress_text)
        self.bind(eta_text=self._update_eta)

    def _update_name(self, *args):
        self._name_label.text = self.item_name

    def _update_type(self, *args):
        self._icon.icon = ICON_MAP.get(self.item_type, "book-open-variant")
        self._type_label.text = self.item_type.replace("_", " ").title()

    def _update_progress(self, *args):
        self._progress_bar.value = self.progress_pct

    def _update_progress_text(self, *args):
        self._progress_label.text = self.progress_text

    def _update_eta(self, *args):
        self._eta_label.text = self.eta_text
