from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QMenuBar, QMenu
from PySide6.QtGui import QFont, QIcon, QAction
from PySide6.QtCore import Qt

from ui.downloads_page import DownloadsPage
from ui.settings_page import SettingsPage
from settings.store import SettingsStore
from ui.i18n import tr, i18n
from core.version import __version__


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{tr('app.title')} v{__version__}")
        self._settings = SettingsStore.load()
        self._apply_geometry()

        self.downloads = DownloadsPage()
        self.setCentralWidget(self.downloads)

        self.settings_window = None
        self._setup_menubar()
        i18n.language_changed.connect(self.retranslate)

    def _setup_menubar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background: #0f1524;
                color: #eaeaea;
                border-bottom: 1px solid #2a3a5a;
                padding: 4px 8px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #2a3a5a;
            }
        """)

        file_menu = menubar.addMenu(tr("menu.file"))
        import_action = QAction(tr("menu.import_urls"), self)
        import_action.triggered.connect(self.downloads.import_urls)
        file_menu.addAction(import_action)

        settings_action = QAction(tr("menu.settings"), self)
        settings_action.triggered.connect(self.open_settings)
        menubar.addAction(settings_action)
        self._file_menu = file_menu
        self._import_action = import_action
        self._settings_action = settings_action

    def open_settings(self):
        if self.settings_window is None:
            self.settings_window = QMainWindow()
            self.settings_window.setWindowTitle(tr("settings.title"))
            self._apply_settings_geometry()
            self.settings_window.setCentralWidget(SettingsPage())
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _apply_geometry(self):
        s = self._settings
        self.setGeometry(s.window_x, s.window_y, s.window_w, s.window_h)

    def _apply_settings_geometry(self):
        s = self._settings
        self.settings_window.setGeometry(s.settings_x, s.settings_y, s.settings_w, s.settings_h)

    def _save_geometry(self):
        s = self._settings
        g = self.geometry()
        s.window_x, s.window_y, s.window_w, s.window_h = g.x(), g.y(), g.width(), g.height()
        if self.settings_window is not None:
            gs = self.settings_window.geometry()
            s.settings_x, s.settings_y, s.settings_w, s.settings_h = gs.x(), gs.y(), gs.width(), gs.height()
        SettingsStore.save(s)

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)

    def retranslate(self):
        self.setWindowTitle(f"{tr('app.title')} v{__version__}")
        if self._file_menu:
            self._file_menu.setTitle(tr("menu.file"))
        if self._import_action:
            self._import_action.setText(tr("menu.import_urls"))
        if self._settings_action:
            self._settings_action.setText(tr("menu.settings"))
        if self.settings_window is not None:
            self.settings_window.setWindowTitle(tr("settings.title"))
            if self.settings_window.isVisible():
                current_index = None
                current = self.settings_window.centralWidget()
                if isinstance(current, SettingsPage):
                    current_index = current.nav.currentRow()
                self.settings_window.setCentralWidget(SettingsPage())
                if current_index is not None:
                    new_page = self.settings_window.centralWidget()
                    if isinstance(new_page, SettingsPage):
                        new_page.nav.setCurrentRow(current_index)
        if self.downloads:
            self.downloads.retranslate()


def apply_style(app: QApplication):
    font = QFont("NanumGothic", 10)
    if not QFont("NanumGothic").exactMatch():
        font = QFont("Segoe UI", 10)
    app.setFont(font)

    app.setStyleSheet("""
        QMainWindow, QWidget {
            background: #1a1a2e;
            color: #eaeaea;
        }

        QLineEdit, QTextEdit {
            background: #0f1524;
            border: 1px solid #2a3a5a;
            border-radius: 6px;
            padding: 8px 12px;
            color: #eaeaea;
            selection-background-color: #e94560;
        }
        QLineEdit:focus, QTextEdit:focus {
            border: 1px solid #e94560;
        }

        QComboBox {
            background: #0f1524;
            border: 1px solid #2a3a5a;
            border-radius: 6px;
            padding: 6px 12px;
            min-height: 20px;
        }
        QComboBox:focus {
            border: 1px solid #e94560;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 8px;
        }
        QComboBox QAbstractItemView {
            background: #0f1524;
            border: 1px solid #2a3a5a;
            selection-background-color: #e94560;
        }

        QPushButton {
            background: #2a3a5a;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: #eaeaea;
        }
        QPushButton:hover {
            background: #3a4a6a;
        }
        QPushButton:pressed {
            background: #e94560;
        }
        QPushButton:disabled {
            background: #1a2a3a;
            color: #555;
        }

        QPushButton#downloadButton {
            background: #e94560;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton#downloadButton:hover {
            background: #ff5a75;
        }

        QCheckBox {
            spacing: 8px;
            color: #eaeaea;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 3px;
            border: 1px solid #2a3a5a;
            background: #0f1524;
        }
        QCheckBox::indicator:checked {
            background: #e94560;
            border: 1px solid #e94560;
        }

        QGroupBox {
            border: 1px solid #2a3a5a;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: #e94560;
        }

        QListWidget {
            background: transparent;
            border: none;
            outline: none;
        }
        QListWidget::item {
            padding: 10px 12px;
            border-radius: 6px;
            margin: 2px 0;
        }
        QListWidget::item:hover {
            background: #2a3a5a;
        }
        QListWidget::item:selected {
            background: #e94560;
            color: #fff;
        }

        QScrollArea {
            border: none;
            background: transparent;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 8px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #3a4a6a;
            border-radius: 4px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #e94560;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            background: transparent;
            height: 8px;
        }
        QScrollBar::handle:horizontal {
            background: #3a4a6a;
            border-radius: 4px;
            min-width: 30px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #e94560;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0;
        }

        QFrame#downloadItem {
            background: #0f1524;
            border: 1px solid #2a3a5a;
            border-radius: 8px;
        }
        QFrame#downloadItem:hover {
            border: 1px solid #e94560;
        }

        QFrame#downloadItem QLabel {
            background: transparent;
        }
        QLabel#itemTitle {
            font-weight: 600;
            font-size: 12px;
            color: #eaeaea;
            background: transparent;
        }
        QLabel#itemMeta {
            color: #8892b0;
            font-size: 11px;
            background: transparent;
        }
        QLabel#statusIcon {
            background: transparent;
        }

        QPushButton#errorButton {
            color: #ff6b6b;
            background: transparent;
            border: none;
            padding: 4px 8px;
        }
        QPushButton#errorButton:hover {
            color: #ff8787;
        }

        QProgressBar {
            background: #1a2a3a;
            border: none;
            border-radius: 2px;
            height: 4px;
        }
        QProgressBar::chunk {
            background: #e94560;
            border-radius: 2px;
        }

        QSpinBox {
            background: #0f1524;
            border: 1px solid #2a3a5a;
            border-radius: 6px;
            padding: 4px 8px;
            color: #eaeaea;
        }
        QSpinBox:focus {
            border: 1px solid #e94560;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            background: #2a3a5a;
            border: none;
            width: 18px;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background: #3a4a6a;
        }

        QToolTip {
            background: #0f1524;
            color: #eaeaea;
            border: 1px solid #2a3a5a;
            padding: 4px 8px;
        }

        QMenu {
            background: #0f1524;
            border: 1px solid #2a3a5a;
            border-radius: 6px;
            padding: 4px;
        }
        QMenu::item {
            padding: 8px 20px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background: #e94560;
        }
        QMenu::separator {
            height: 1px;
            background: #2a3a5a;
            margin: 4px 8px;
        }
    """)


def main():
    app = QApplication([])
    apply_style(app)
    win = MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()
