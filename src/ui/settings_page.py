from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget,
    QLabel, QGroupBox, QFormLayout, QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QKeySequence, QShortcut, QDesktopServices
import shutil
import os
import sys
import zipfile
import urllib.request
import threading
import tempfile

from settings.store import SettingsStore
from ui.widgets import path_picker, labeled_textarea, labeled_edit, file_picker
from ui.i18n import tr, i18n


class SettingsPage(QWidget):
    NAV_ITEMS = [
        ("⚙", "settings.nav.general"),
        ("📁", "settings.nav.download"),
        ("📝", "settings.nav.subs_meta"),
        ("🔑", "settings.nav.auth"),
        ("⏭", "settings.nav.sponsorblock"),
        ("🧰", "settings.nav.bundle"),
    ]

    BROWSER_OPTIONS = [
        ("chrome", "Chrome"),
        ("firefox", "Firefox"),
        ("edge", "Edge"),
        ("opera", "Opera"),
        ("brave", "Brave"),
        ("vivaldi", "Vivaldi"),
        ("safari", "Safari"),
    ]

    REMOTE_COMPONENT_OPTIONS = [
        ("ejs:github", "settings.option.remote_components.github"),
        ("", "settings.option.remote_components.off"),
    ]

    PLAYER_CLIENT_OPTIONS = [
        ("", "settings.option.player_clients.auto"),
        ("web", "settings.option.player_clients.web"),
        ("web,android", "settings.option.player_clients.web_android"),
    ]

    LANGUAGE_OPTIONS = [
        ("English", "English"),
        ("Korean", "한국어"),
        ("Japanese", "日本語"),
        ("Chinese (Simplified)", "简体中文"),
        ("Chinese (Traditional)", "繁體中文"),
    ]

    def __init__(self):
        super().__init__()
        self.settings = SettingsStore.load()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav_panel = QWidget()
        nav_panel.setFixedWidth(150)
        nav_panel.setStyleSheet("""
            QWidget {
                background: #0f1524;
                border-right: 1px solid #2a3a5a;
            }
        """)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(8, 12, 8, 12)
        nav_layout.setSpacing(4)

        self.nav = QListWidget()
        for icon, key in self.NAV_ITEMS:
            item = QListWidgetItem(f"{icon}  {tr(key)}")
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        nav_layout.addWidget(self.nav, 1)

        save_btn = QPushButton(tr("settings.save"))
        save_btn.setStyleSheet("""
            QPushButton {
                background: #e94560;
                border: none;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton:hover {
                background: #ff5a75;
            }
        """)
        save_btn.clicked.connect(lambda: self.save())
        nav_layout.addWidget(save_btn)

        root.addWidget(nav_panel)

        content_panel = QWidget()
        content_panel.setStyleSheet("background: #1a1a2e;")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(20, 16, 20, 16)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._page_general())
        self.stack.addWidget(self._page_download())
        self.stack.addWidget(self._page_subs_meta())
        self.stack.addWidget(self._page_auth())
        self.stack.addWidget(self._page_sponsorblock())
        self.stack.addWidget(self._page_bundle())

        root.addWidget(content_panel, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        QShortcut(QKeySequence.Save, self, activated=self.save)

    def _format_options(self):
        return [
            ("mp4", tr("settings.format.mp4")),
            ("mkv", tr("settings.format.mkv")),
            ("webm", tr("settings.format.webm")),
            ("mp3", tr("settings.format.mp3_audio")),
            ("m4a", tr("settings.format.m4a_audio")),
            ("opus", tr("settings.format.opus_audio")),
            ("flac", tr("settings.format.flac_audio")),
        ]

    def _video_quality_options(self):
        return [
            ("best", tr("settings.video_quality.best")),
            ("2160p", tr("settings.video_quality.2160p")),
            ("1440p", tr("settings.video_quality.1440p")),
            ("1080p", tr("settings.video_quality.1080p")),
            ("720p", tr("settings.video_quality.720p")),
            ("480p", tr("settings.video_quality.480p")),
            ("360p", tr("settings.video_quality.360p")),
            ("audio_only", tr("settings.video_quality.audio_only")),
        ]

    def _audio_quality_options(self):
        return [
            ("best", tr("settings.audio_quality.best")),
            ("320k", "320 kbps"),
            ("256k", "256 kbps"),
            ("192k", "192 kbps"),
            ("128k", "128 kbps"),
            ("96k", "96 kbps"),
        ]

    def _wrap_scroll(self, widget: QWidget):
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(widget)
        return area

    def _section_header(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #e94560;
            padding: 2px 0 6px 0;
            border-bottom: 1px solid #2a3a5a;
            margin-bottom: 6px;
        """)
        return lbl

    def _combo_row(self, label: str, options: list, current_value: str):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setMinimumWidth(100)
        combo = QComboBox()

        current_idx = 0
        for i, (value, display) in enumerate(options):
            combo.addItem(display, value)
            if value == current_value:
                current_idx = i
        combo.setCurrentIndex(current_idx)

        layout.addWidget(lbl)
        layout.addWidget(combo, 1)
        return row, combo

    def _spin_row(self, label: str, value: int, min_val: int, max_val: int):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setMinimumWidth(100)
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        spin.setFixedWidth(80)

        layout.addWidget(lbl)
        layout.addWidget(spin)
        layout.addStretch(1)
        return row, spin

    def _page_general(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(self._section_header(tr("settings.section.language")))

        lang_row, self.language = self._combo_row(tr("settings.label.language"), self.LANGUAGE_OPTIONS, self.settings.language)
        self.language.currentIndexChanged.connect(lambda: self.save(close_window=False))
        layout.addWidget(lang_row)

        layout.addWidget(self._section_header(tr("settings.section.general")))

        path_row, self.download_dir = path_picker(tr("settings.label.download_dir"), "ytdl")
        self.download_dir.setText(self.settings.download_dir)
        layout.addWidget(path_row)

        out_row, self.out_default = labeled_edit(tr("settings.label.outtmpl_default"), "[%(uploader)s] %(title)s (%(id)s).%(ext)s")
        self.out_default.setText(self.settings.outtmpl_default)
        layout.addWidget(out_row)

        pl_row, self.out_playlist = labeled_edit(tr("settings.label.outtmpl_playlist"), "[Playlist] %(playlist_title)s/%(playlist_index)03d. %(title)s.%(ext)s")
        self.out_playlist.setText(self.settings.outtmpl_playlist)
        layout.addWidget(pl_row)

        help_lbl = QLabel(tr("settings.help.templates"))
        help_lbl.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(help_lbl)

        layout.addStretch(1)
        return self._wrap_scroll(page)

    def _page_download(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(self._section_header(tr("settings.section.download")))

        fmt_row, self.output_format = self._combo_row(tr("settings.label.output_format"), self._format_options(), self.settings.output_format)
        layout.addWidget(fmt_row)

        vq_row, self.video_quality = self._combo_row(tr("settings.label.video_quality"), self._video_quality_options(), self.settings.video_quality)
        layout.addWidget(vq_row)

        aq_row, self.audio_quality = self._combo_row(tr("settings.label.audio_quality"), self._audio_quality_options(), self.settings.audio_quality)
        layout.addWidget(aq_row)

        frag_row, self.fragments = self._spin_row(tr("settings.label.concurrent_fragments"), self.settings.concurrent_fragments, 1, 16)
        layout.addWidget(frag_row)

        retry_row, self.retries = self._spin_row(tr("settings.label.retries"), self.settings.retries, 1, 30)
        layout.addWidget(retry_row)

        self.verify_download = QCheckBox(tr("settings.option.verify_download"))
        self.verify_download.setChecked(self.settings.verify_download)
        self.verify_download.setToolTip(tr("settings.tooltip.verify_download"))
        layout.addWidget(self.verify_download)

        self.prefer_largest_file = QCheckBox(tr("settings.option.prefer_largest_file"))
        self.prefer_largest_file.setChecked(self.settings.prefer_largest_file)
        layout.addWidget(self.prefer_largest_file)

        layout.addStretch(1)
        return self._wrap_scroll(page)

    def _page_subs_meta(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(self._section_header(tr("settings.section.subtitles")))

        self.write_subs = QCheckBox(tr("settings.option.write_subs"))
        self.write_subs.setChecked(self.settings.write_subs)
        layout.addWidget(self.write_subs)

        self.write_auto_subs = QCheckBox(tr("settings.option.write_auto_subs"))
        self.write_auto_subs.setChecked(self.settings.write_auto_subs)
        layout.addWidget(self.write_auto_subs)

        sub_row, self.sub_langs = labeled_edit(tr("settings.label.sub_langs"), "ko,en")
        self.sub_langs.setText(self.settings.sub_langs)
        self.sub_langs.setToolTip(tr("settings.tooltip.sub_langs"))
        layout.addWidget(sub_row)

        self.embed_subs = QCheckBox(tr("settings.option.embed_subs"))
        self.embed_subs.setChecked(self.settings.embed_subs)
        layout.addWidget(self.embed_subs)

        layout.addWidget(self._section_header(tr("settings.section.metadata")))

        self.embed_thumbnail = QCheckBox(tr("settings.option.embed_thumbnail"))
        self.embed_thumbnail.setChecked(self.settings.embed_thumbnail)
        layout.addWidget(self.embed_thumbnail)

        self.embed_chapters = QCheckBox(tr("settings.option.embed_chapters"))
        self.embed_chapters.setChecked(self.settings.embed_chapters)
        layout.addWidget(self.embed_chapters)

        self.write_thumbnail = QCheckBox(tr("settings.option.write_thumbnail"))
        self.write_thumbnail.setChecked(self.settings.write_thumbnail)
        layout.addWidget(self.write_thumbnail)

        self.add_metadata = QCheckBox(tr("settings.option.add_metadata"))
        self.add_metadata.setChecked(self.settings.add_metadata)
        layout.addWidget(self.add_metadata)

        layout.addStretch(1)
        return self._wrap_scroll(page)

    def _page_auth(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(self._section_header(tr("settings.section.youtube")))

        pc_row, self.yt_player_clients = self._combo_row(
            tr("settings.label.yt_player_clients"),
            [(v, tr(k)) for v, k in self.PLAYER_CLIENT_OPTIONS],
            self.settings.yt_player_clients,
        )
        layout.addWidget(pc_row)

        rc_row, self.yt_remote_components = self._combo_row(
            tr("settings.label.yt_remote_components"),
            [(v, tr(k)) for v, k in self.REMOTE_COMPONENT_OPTIONS],
            self.settings.yt_remote_components,
        )
        layout.addWidget(rc_row)

        token_row, self.yt_po_token = labeled_edit(tr("settings.label.yt_po_token"), "android.gvs+TOKEN")
        self.yt_po_token.setText(self.settings.yt_po_token)
        layout.addWidget(token_row)

        token_help = QLabel(tr("settings.help.yt_po_token"))
        token_help.setStyleSheet("color: #6b7280; font-size: 10px; padding: 2px 0;")
        layout.addWidget(token_help)

        self.deno_warn = QLabel(tr("settings.warning.deno_missing"))
        self.deno_warn.setStyleSheet("color: #ffb703; font-size: 10px; padding: 2px 0;")
        layout.addWidget(self.deno_warn)

        self.ffmpeg_warn = QLabel(tr("settings.warning.ffmpeg_missing"))
        self.ffmpeg_warn.setStyleSheet("color: #ffb703; font-size: 10px; padding: 2px 0;")
        layout.addWidget(self.ffmpeg_warn)

        self._update_deno_warning()
        self.yt_remote_components.currentIndexChanged.connect(self._update_deno_warning)

        layout.addWidget(self._section_header(tr("settings.section.browser_cookies")))

        desc = QLabel(tr("settings.help.cookies_desc"))
        desc.setStyleSheet("color: #8892b0; font-size: 11px; padding: 4px 0;")
        layout.addWidget(desc)

        self.use_cookies_from_browser = QCheckBox(tr("settings.option.use_cookies_from_browser"))
        self.use_cookies_from_browser.setChecked(self.settings.use_cookies_from_browser)
        layout.addWidget(self.use_cookies_from_browser)

        browser_row, self.cookies_from_browser = self._combo_row(tr("settings.label.cookies_browser"), self.BROWSER_OPTIONS, self.settings.cookies_from_browser)
        self.cookies_from_browser.setEnabled(self.settings.use_cookies_from_browser)
        self.use_cookies_from_browser.toggled.connect(self.cookies_from_browser.setEnabled)
        layout.addWidget(browser_row)

        layout.addWidget(self._section_header(tr("settings.section.age_restricted")))

        self.enable_age_restricted = QCheckBox(tr("settings.option.enable_age_restricted"))
        self.enable_age_restricted.setChecked(self.settings.enable_age_restricted)
        self.enable_age_restricted.setToolTip(tr("settings.tooltip.age_restricted"))
        layout.addWidget(self.enable_age_restricted)

        age_desc = QLabel(tr("settings.help.age_desc"))
        age_desc.setStyleSheet("color: #6b7280; font-size: 10px; padding: 4px 0;")
        layout.addWidget(age_desc)

        layout.addWidget(self._section_header(tr("settings.section.cookies_file")))

        file_row, self.cookies_text = labeled_textarea(tr("settings.label.cookies_text"), tr("settings.placeholder.cookies_text"))
        self.cookies_text.setPlainText(self.settings.cookies_text)
        self.cookies_text.setToolTip(tr("settings.tooltip.cookies_text"))
        layout.addWidget(file_row)

        layout.addStretch(1)
        return self._wrap_scroll(page)

    def _page_sponsorblock(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(self._section_header(tr("settings.section.sponsorblock")))

        desc = QLabel(tr("settings.help.sponsorblock_desc"))
        desc.setStyleSheet("color: #8892b0; font-size: 11px; padding: 4px 0;")
        layout.addWidget(desc)

        self.sb_enable = QCheckBox(tr("settings.option.sponsorblock_enable"))
        self.sb_enable.setChecked(self.settings.sponsorblock_enable)
        layout.addWidget(self.sb_enable)

        cat_desc = QLabel(tr("settings.help.sponsorblock_cats"))
        cat_desc.setStyleSheet("color: #6b7280; font-size: 10px; padding: 4px 0;")
        cat_desc.setWordWrap(True)
        layout.addWidget(cat_desc)

        remove_row, self.sb_remove = labeled_edit(tr("settings.label.sb_remove"), "sponsor,intro,outro")
        self.sb_remove.setText(self.settings.sponsorblock_remove)
        self.sb_remove.setToolTip(tr("settings.tooltip.sub_langs"))
        layout.addWidget(remove_row)

        mark_row, self.sb_mark = labeled_edit(tr("settings.label.sb_mark"), "")
        self.sb_mark.setText(self.settings.sponsorblock_mark)
        self.sb_mark.setToolTip(tr("settings.tooltip.sponsorblock_mark"))
        layout.addWidget(mark_row)

        layout.addStretch(1)
        return self._wrap_scroll(page)

    def _page_bundle(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        layout.addWidget(self._section_header(tr("settings.section.bundle")))

        deno_row, self.bundle_deno = labeled_edit(tr("settings.label.bundle.deno"), "")
        self.bundle_deno.setReadOnly(True)
        layout.addWidget(deno_row)

        deno_path_row, self.bundle_deno_path = labeled_edit(tr("settings.label.bundle.path"), "")
        self.bundle_deno_path.setReadOnly(True)
        layout.addWidget(deno_path_row)

        deno_override_row, self.bundle_deno_override = file_picker(tr("settings.label.bundle.override"), "")
        self.bundle_deno_override.setText(self.settings.deno_path)
        layout.addWidget(deno_override_row)

        ffmpeg_row, self.bundle_ffmpeg = labeled_edit(tr("settings.label.bundle.ffmpeg"), "")
        self.bundle_ffmpeg.setReadOnly(True)
        layout.addWidget(ffmpeg_row)

        ffmpeg_path_row, self.bundle_ffmpeg_path = labeled_edit(tr("settings.label.bundle.path"), "")
        self.bundle_ffmpeg_path.setReadOnly(True)
        layout.addWidget(ffmpeg_path_row)

        ffmpeg_override_row, self.bundle_ffmpeg_override = file_picker(tr("settings.label.bundle.override"), "")
        self.bundle_ffmpeg_override.setText(self.settings.ffmpeg_path)
        layout.addWidget(ffmpeg_override_row)

        btns = QHBoxLayout()
        btns.setSpacing(8)
        refresh_btn = QPushButton(tr("settings.button.bundle.refresh"))
        refresh_btn.clicked.connect(self._refresh_bundle_status)
        download_btn = QPushButton(tr("settings.button.bundle.download"))
        download_btn.clicked.connect(self._open_bundle_downloads)
        btns.addStretch(1)
        btns.addWidget(refresh_btn)
        btns.addWidget(download_btn)
        layout.addLayout(btns)

        help_lbl = QLabel(tr("settings.help.bundle.download"))
        help_lbl.setStyleSheet("color: #6b7280; font-size: 10px; padding: 2px 0;")
        layout.addWidget(help_lbl)

        self._refresh_bundle_status()
        layout.addStretch(1)
        return self._wrap_scroll(page)

    def save(self, close_window: bool = True):
        s = self.settings
        prev_language = s.language

        s.language = self.language.currentData()
        s.download_dir = self.download_dir.text().strip()
        s.outtmpl_default = self.out_default.text().strip()
        s.outtmpl_playlist = self.out_playlist.text().strip()

        s.output_format = self.output_format.currentData()
        s.video_quality = self.video_quality.currentData()
        s.audio_quality = self.audio_quality.currentData()
        s.concurrent_fragments = self.fragments.value()
        s.retries = self.retries.value()
        s.verify_download = self.verify_download.isChecked()
        s.prefer_largest_file = self.prefer_largest_file.isChecked()

        s.write_subs = self.write_subs.isChecked()
        s.write_auto_subs = self.write_auto_subs.isChecked()
        s.sub_langs = self.sub_langs.text().strip()
        s.embed_subs = self.embed_subs.isChecked()
        s.write_thumbnail = self.write_thumbnail.isChecked()
        s.embed_thumbnail = self.embed_thumbnail.isChecked()
        s.embed_chapters = self.embed_chapters.isChecked()
        s.add_metadata = self.add_metadata.isChecked()

        s.use_cookies_from_browser = self.use_cookies_from_browser.isChecked()
        s.cookies_from_browser = self.cookies_from_browser.currentData()
        s.cookies_text = self.cookies_text.toPlainText().strip()
        s.cookies_file = SettingsStore.write_cookies_text(s.cookies_text)
        s.enable_age_restricted = self.enable_age_restricted.isChecked()
        s.yt_remote_components = self.yt_remote_components.currentData()
        s.yt_player_clients = self.yt_player_clients.currentData()
        s.yt_po_token = self.yt_po_token.text().strip()
        s.deno_path = self.bundle_deno_override.text().strip()
        s.ffmpeg_path = self.bundle_ffmpeg_override.text().strip()

        s.sponsorblock_enable = self.sb_enable.isChecked()
        s.sponsorblock_remove = self.sb_remove.text().strip()
        s.sponsorblock_mark = self.sb_mark.text().strip()

        SettingsStore.save(s)
        if close_window:
            window = self.window()
            if window is not None:
                window.close()
        if prev_language != s.language:
            i18n.notify_language_changed()

    def _update_deno_warning(self):
        enabled = bool(self.yt_remote_components.currentData())
        has_deno = bool(self._detect_deno_path())
        self.deno_warn.setVisible(enabled and not has_deno)
        self._update_ffmpeg_warning()

    def _update_ffmpeg_warning(self):
        has_ffmpeg = bool(self._detect_ffmpeg_path())
        self.ffmpeg_warn.setVisible(not has_ffmpeg)

    def _refresh_bundle_status(self):
        def status(has_tool: bool) -> str:
            return tr("settings.value.bundle.present") if has_tool else tr("settings.value.bundle.missing")

        deno_path = self._detect_deno_path()
        ffmpeg_path = self._detect_ffmpeg_path()
        has_deno = bool(deno_path)
        has_ffmpeg = bool(ffmpeg_path)

        if hasattr(self, "bundle_deno"):
            self.bundle_deno.setText(status(has_deno))
        if hasattr(self, "bundle_ffmpeg"):
            self.bundle_ffmpeg.setText(status(has_ffmpeg))
        if hasattr(self, "bundle_deno_path"):
            self.bundle_deno_path.setText(deno_path or "")
        if hasattr(self, "bundle_ffmpeg_path"):
            self.bundle_ffmpeg_path.setText(ffmpeg_path or "")
        if hasattr(self, "bundle_deno_override") and deno_path:
            self.bundle_deno_override.setText(deno_path)
        if hasattr(self, "bundle_ffmpeg_override") and ffmpeg_path:
            self.bundle_ffmpeg_override.setText(ffmpeg_path)

        changed = False
        if deno_path and self.settings.deno_path != deno_path:
            self.settings.deno_path = deno_path
            changed = True
        if ffmpeg_path and self.settings.ffmpeg_path != ffmpeg_path:
            self.settings.ffmpeg_path = ffmpeg_path
            changed = True
        if changed:
            SettingsStore.save(self.settings)
            self._update_deno_warning()

    def _open_bundle_downloads(self):
        self._start_bundle_download()

    def _start_bundle_watch(self):
        if not hasattr(self, "_bundle_timer"):
            self._bundle_timer = QTimer(self)
            self._bundle_timer.timeout.connect(self._on_bundle_watch_tick)
        self._bundle_watch_ticks = 0
        self._bundle_timer.start(2000)

    def _on_bundle_watch_tick(self):
        self._bundle_watch_ticks += 1
        self._refresh_bundle_status()
        if self._bundle_watch_ticks >= 30:
            self._bundle_timer.stop()

    def _start_bundle_download(self):
        if getattr(self, "_bundle_downloading", False):
            return
        self._bundle_downloading = True

        def worker():
            try:
                bundle_dir = self._bundle_dir()
                os.makedirs(bundle_dir, exist_ok=True)
                deno_zip = self._download_to(bundle_dir, "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip")
                deno_path = self._extract_and_find(deno_zip, bundle_dir, "deno.exe")

                ffmpeg_zip = self._download_to(bundle_dir, "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")
                ffmpeg_path = self._extract_and_find(ffmpeg_zip, bundle_dir, "ffmpeg.exe")
                self._extract_and_find(ffmpeg_zip, bundle_dir, "ffprobe.exe")

                def apply_update():
                    if deno_path:
                        self.bundle_deno_override.setText(deno_path)
                    if ffmpeg_path:
                        self.bundle_ffmpeg_override.setText(ffmpeg_path)
                    self.save(close_window=False)
                    self._refresh_bundle_status()

                QTimer.singleShot(0, apply_update)
            finally:
                self._bundle_downloading = False

        threading.Thread(target=worker, daemon=True).start()
        self._start_bundle_watch()

    def _bundle_dir(self) -> str:
        if getattr(sys, "frozen", False):
            return os.path.join(os.path.dirname(sys.executable), "bundle")
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "bundle")

    def _download_to(self, dest_dir: str, url: str) -> str:
        fd, tmp_path = tempfile.mkstemp(suffix=".zip", dir=dest_dir)
        os.close(fd)
        urllib.request.urlretrieve(url, tmp_path)
        return tmp_path

    def _extract_and_find(self, zip_path: str, dest_dir: str, filename: str) -> str:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_dir)
        except Exception:
            return ""
        for root, _dirs, files in os.walk(dest_dir):
            if filename in files:
                return os.path.join(root, filename)
        return ""

    def _detect_deno_path(self) -> str:
        override = self.settings.deno_path.strip()
        if override and os.path.exists(override):
            return override
        found = self._find_in_bundle_or_meipass("deno.exe")
        if found:
            return found
        path = shutil.which("deno")
        if path and "WinGet\\Links" not in path:
            return path
        return self._scan_winget_packages("deno.exe")

    def _detect_ffmpeg_path(self) -> str:
        override = self.settings.ffmpeg_path.strip()
        if override and os.path.exists(override):
            return override
        found = self._find_in_bundle_or_meipass("ffmpeg.exe")
        if found:
            return found
        path = shutil.which("ffmpeg")
        if path and "WinGet\\Links" not in path:
            return path
        candidates = [
            os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "chocolatey", "lib"),
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "ffmpeg"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "ffmpeg"),
        ]
        for base in candidates:
            for root, _dirs, files in os.walk(base):
                if "ffmpeg.exe" in files:
                    return os.path.join(root, "ffmpeg.exe")
        return self._scan_winget_packages("ffmpeg.exe")

    def _find_in_bundle_or_meipass(self, exe_name: str) -> str:
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", "")
            if base:
                candidate = os.path.join(base, exe_name)
                if os.path.exists(candidate):
                    return candidate
        bundle_candidate = os.path.join(self._bundle_dir(), exe_name)
        if os.path.exists(bundle_candidate):
            return bundle_candidate
        bundle_dir = self._bundle_dir()
        if os.path.exists(bundle_dir):
            for root, _dirs, files in os.walk(bundle_dir):
                if exe_name in files:
                    return os.path.join(root, exe_name)
        app_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(app_dir, exe_name)
        if os.path.exists(candidate):
            return candidate
        return ""

    def _scan_winget_packages(self, exe_name: str) -> str:
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")
        if not base or not os.path.exists(base):
            return ""
        for root, _dirs, files in os.walk(base):
            if exe_name in files:
                return os.path.join(root, exe_name)
        return ""
