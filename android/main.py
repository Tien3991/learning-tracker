import os
import sys

# Ensure the android directory is on sys.path so local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import platform
from kivymd.app import MDApp

from db import init_db
from screens.list_screen import ListScreen, Tab
from screens.detail_screen import DetailScreen
from screens.add_item_screen import AddItemScreen

# Load KV files
KV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kv")

# Phone-like window on desktop for testing
if platform not in ("android", "ios"):
    Window.size = (400, 700)

# Prevent keyboard from overlapping content
Window.softinput_mode = "below_target"


class LearningTrackerApp(MDApp):

    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.material_style = "M3"

        # Load KV files
        for kv_file in ("list_screen.kv", "detail_screen.kv", "add_item_screen.kv"):
            Builder.load_file(os.path.join(KV_DIR, kv_file))

        # Init database
        init_db()

        # Build screen manager
        from kivy.uix.screenmanager import ScreenManager
        sm = ScreenManager()
        sm.add_widget(ListScreen(name="list"))
        sm.add_widget(DetailScreen(name="detail"))
        sm.add_widget(AddItemScreen(name="add_item"))

        # Bind back button
        Window.bind(on_keyboard=self._on_keyboard)

        return sm

    def _on_keyboard(self, window, key, *args):
        if key == 27:  # ESC / Android back button
            sm = self.root
            if sm.current != "list":
                self.go_to_list()
                return True  # Consume the event
            # On list screen, let the system handle it (exit app)
        return False

    def go_to_list(self):
        self.root.transition.direction = "right"
        self.root.current = "list"

    def go_to_detail(self, item_id):
        detail_screen = self.root.get_screen("detail")
        detail_screen.item_id = item_id
        self.root.transition.direction = "left"
        self.root.current = "detail"

    def go_to_add_item(self):
        self.root.transition.direction = "left"
        self.root.current = "add_item"


if __name__ == "__main__":
    LearningTrackerApp().run()
