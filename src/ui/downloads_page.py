import csv
import os
import re
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFrame, QCheckBox, QDialog, QTextEdit, QMenu, QFileDialog,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal
from urllib.parse import urlparse, parse_qs, urlencode
from PySide6.QtGui import QPixmap
import requests

from settings.store import SettingsStore
from core.ytdlp_runner import YtdlpRunner
from ui.i18n import tr, i18n


class UrlInput(QLineEdit):
    submit = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return and event.modifiers() & Qt.ControlModifier:
            self.submit.emit()
            return
        super().keyPressEvent(event)


class ErrorDialog(QDialog):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("downloads.error_title"))
        self.resize(640, 400)
        self.setStyleSheet("""
            QDialog {
                background: #1a1a2e;
            }
            QTextEdit {
                background: #0f1524;
                border: 1px solid #2a3a5a;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'D2Coding', monospace;
                font-size: 11px;
                color: #ff6b6b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(tr("downloads.error_header"))
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff6b6b;")
        layout.addWidget(header)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(text)
        layout.addWidget(self.text, 1)

        btns = QHBoxLayout()
        btns.setSpacing(8)

        copy_btn = QPushButton(tr("downloads.error_copy"))
        copy_btn.clicked.connect(self.copy)

        close_btn = QPushButton(tr("downloads.error_close"))
        close_btn.setStyleSheet("""
            QPushButton {
                background: #e94560;
            }
            QPushButton:hover {
                background: #ff5a75;
            }
        """)
        close_btn.clicked.connect(self.accept)

        btns.addStretch(1)
        btns.addWidget(copy_btn)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def copy(self):
        self.text.selectAll()
        self.text.copy()


class DownloadItem(QFrame):
    STATUS_ICONS = {
        "queued": "⏳",
        "running": "⬇",
        "done": "✓",
        "error": "✗",
    }

    def __init__(self, title: str, meta: str, error: str = "", *, on_context=None, state: str = "queued"):
        super().__init__()
        self.setObjectName("downloadItem")
        self._on_context = on_context
        self._state = state

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        self.thumb = QLabel()
        self.thumb.setFixedSize(72, 40)
        self.thumb.setStyleSheet("background: #1a2a3a; border-radius: 4px;")
        top_layout.addWidget(self.thumb)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self.status_icon = QLabel(self.STATUS_ICONS.get(state, "⏳"))
        self.status_icon.setObjectName("statusIcon")
        self.status_icon.setFixedWidth(20)
        self._update_status_icon_color()
        title_row.addWidget(self.status_icon)

        self.title_lbl = QLabel(title)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setObjectName("itemTitle")
        title_row.addWidget(self.title_lbl, 1)

        text_box.addLayout(title_row)

        self.meta_lbl = QLabel(meta)
        self.meta_lbl.setObjectName("itemMeta")
        text_box.addWidget(self.meta_lbl)

        top_layout.addLayout(text_box, 1)

        self.err_btn = QPushButton(tr("downloads.error_button"))
        self.err_btn.setObjectName("errorButton")
        self.err_btn.setFlat(True)
        self.err_btn.setVisible(False)
        self.err_btn.clicked.connect(lambda: self.show_error(error))
        top_layout.addWidget(self.err_btn)

        main_layout.addLayout(top_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        if error:
            self.set_error(error)

    def show_error(self, text: str):
        dlg = ErrorDialog(text, self)
        dlg.exec()

    def set_meta(self, meta: str):
        self.meta_lbl.setText(meta)

    def set_state(self, state: str):
        self._state = state
        self.status_icon.setText(self.STATUS_ICONS.get(state, "⏳"))
        self._update_status_icon_color()
        self.progress_bar.setVisible(state == "running")
        if state == "done":
            self.progress_bar.setValue(100)
        elif state == "error":
            self.progress_bar.setValue(0)

    def set_progress(self, percent: float):
        self.progress_bar.setValue(int(percent))
        if percent > 0:
            self.progress_bar.setVisible(True)

    def _update_status_icon_color(self):
        colors = {
            "queued": "#8892b0",
            "running": "#e94560",
            "done": "#4ade80",
            "error": "#ff6b6b",
        }
        color = colors.get(self._state, "#8892b0")
        self.status_icon.setStyleSheet(f"color: {color}; font-size: 14px;")

    def set_error(self, text: str):
        if not text:
            self.err_btn.setVisible(False)
            try:
                self.err_btn.clicked.disconnect()
            except Exception:
                pass
            return
        self.err_btn.setVisible(True)
        self.set_state("error")
        try:
            self.err_btn.clicked.disconnect()
        except Exception:
            pass
        self.err_btn.clicked.connect(lambda: self.show_error(text))

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap.isNull():
            return
        self.thumb.setPixmap(pixmap.scaled(72, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def contextMenuEvent(self, event):
        if self._on_context:
            self._on_context(event.globalPos())
        else:
            super().contextMenuEvent(event)


class DownloadsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._seen_clipboard = set()
        self._workers = {}
        self._items = {}
        self._item_seq = 0
        self._loaded = False
        self._settings = SettingsStore.load()
        self._sort_desc = self._settings.list_sort_desc
        self._thumb_dir = self._get_thumb_dir()
        os.makedirs(self._thumb_dir, exist_ok=True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.list_area = QScrollArea()
        self.list_area.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.list_area.setWidget(self.content)
        root.addWidget(self.list_area, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 8, 0, 0)
        bottom.setSpacing(8)

        self.url_input = UrlInput()
        self.url_input.setPlaceholderText(tr("downloads.url_placeholder"))
        self.url_input.submit.connect(self.start_download)

        self.clipboard_toggle = QCheckBox(tr("downloads.clipboard"))
        self.clipboard_toggle.setToolTip(tr("downloads.clipboard_tooltip"))
        self.clipboard_toggle.setChecked(self._settings.clipboard_enabled)
        self.clipboard_toggle.toggled.connect(self.on_clipboard_toggle)

        self.sort_btn = QPushButton()
        self.sort_btn.setFixedWidth(90)
        self.sort_btn.clicked.connect(self.toggle_sort)
        self._update_sort_button()

        self.download_btn = QPushButton(tr("downloads.download_button"))
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.setMinimumWidth(90)
        self.download_btn.clicked.connect(self.start_download)

        bottom.addWidget(self.url_input, 1)
        bottom.addWidget(self.clipboard_toggle)
        bottom.addWidget(self.sort_btn)
        bottom.addWidget(self.download_btn)
        root.addLayout(bottom)

        self._load_list_csv()
        self._loaded = True
        if self.clipboard_toggle.isChecked():
            self.on_clipboard_toggle(True)
        i18n.language_changed.connect(self.retranslate)

    def add_item(self, title: str, meta: str, error: str = "", urls=None, item_id=None, state="queued", locked=False, log_path=""):
        if self._loaded:
            created_at = datetime.utcnow().isoformat()
        else:
            created_at = None
        if item_id is None:
            self._item_seq += 1
            item_id = self._item_seq
        else:
            self._item_seq = max(self._item_seq, item_id)
        item = DownloadItem(title, meta, error, on_context=lambda pos, i=item_id: self._show_menu(i, pos), state=state)
        self.content_layout.insertWidget(self.content_layout.count() - 1, item)
        if created_at is None:
            created_at = datetime.utcnow().isoformat()
        self._items[item_id] = {
            "id": item_id,
            "title": title,
            "status": meta,
            "state": state,
            "urls": urls or [],
            "locked": locked,
            "error": error,
            "created_at": created_at,
            "updated_at": datetime.utcnow().isoformat(),
            "log_path": log_path,
            "thumb_path": "",
            "widget": item,
        }
        self._save_list_csv()
        self._reorder_items()
        return item_id

    def parse_urls(self, text: str):
        raw = [t.strip() for t in text.replace("\r", "").split("\n")]
        urls = []
        for line in raw:
            if not line:
                continue
            parts = line.split()
            urls.extend(parts)
        return [u for u in urls if self._is_valid_url(u)]

    def _is_valid_url(self, url: str) -> bool:
        try:
            p = urlparse(url)
            if p.scheme not in ("http", "https"):
                return False
            host = (p.netloc or "").lower()
            return "youtube.com" in host or "youtu.be" in host
        except Exception:
            return False

    def normalize_youtube_url(self, url: str):
        try:
            p = urlparse(url)
            qs = parse_qs(p.query)
            host = p.netloc.lower()
            if "youtube.com" in host and p.path == "/playlist":
                return url
            if "youtu.be" in host and "list" in qs:
                return f"{p.scheme}://{p.netloc}{p.path}"
            if "youtube.com" in host and p.path == "/watch" and "list" in qs:
                v = qs.get("v", [""])[0]
                if v:
                    return f"{p.scheme}://{p.netloc}{p.path}?{urlencode({'v': v})}"
        except Exception:
            return url
        return url

    def is_playlist_url(self, url: str) -> bool:
        try:
            p = urlparse(url)
            host = p.netloc.lower()
            qs = parse_qs(p.query)
            return "youtube.com" in host and p.path == "/playlist" and "list" in qs
        except Exception:
            return False

    def extract_video_id(self, url: str) -> str:
        try:
            p = urlparse(url)
            host = p.netloc.lower()
            qs = parse_qs(p.query)
            if "youtu.be" in host:
                return p.path.lstrip("/").split("/")[0]
            if "youtube.com" in host and p.path == "/watch":
                return qs.get("v", [""])[0]
            if "youtube.com" in host and p.path.startswith("/shorts/"):
                return p.path.replace("/shorts/", "").split("/")[0]
            if "youtube.com" in host and p.path.startswith("/embed/"):
                return p.path.replace("/embed/", "").split("/")[0]
            if "youtube.com" in host and p.path == "/playlist":
                return f"playlist:{qs.get('list', [''])[0]}"
        except Exception:
            pass
        return ""

    def _get_active_video_ids(self) -> set:
        ids = set()
        for item in self._items.values():
            state = item.get("state", "")
            if state in ("queued", "running", "done"):
                for url in item.get("urls", []):
                    vid = self.extract_video_id(url)
                    if vid:
                        ids.add(vid)
        return ids

    def start_download(self):
        text = self.url_input.text().strip()
        if not text:
            return
        urls = [self.normalize_youtube_url(u) for u in self.parse_urls(text)]
        if not urls:
            return
        self.url_input.clear()
        self.run_ytdlp(urls)

    def import_urls(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("downloads.import_title"), "", tr("downloads.import_filter"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return
        urls = [self.normalize_youtube_url(u) for u in self.parse_urls(text)]
        if not urls:
            return
        self.run_ytdlp(urls)

    def run_ytdlp(self, urls):
        active_ids = self._get_active_video_ids()
        filtered_urls = []
        skipped = 0
        for url in urls:
            vid = self.extract_video_id(url)
            if vid and vid in active_ids:
                skipped += 1
                print(f"Skipped (duplicate): {url}")
                continue
            filtered_urls.append(url)

        if not filtered_urls:
            if skipped > 0:
                print(f"All {skipped} URL(s) skipped (already downloaded or in progress)")
            return

        settings = SettingsStore.load()
        title = filtered_urls[0] if len(filtered_urls) == 1 else tr("downloads.batch").format(count=len(filtered_urls))
        item_id = self.add_item(title, tr("downloads.status.queued"), "", urls=filtered_urls)
        allow_playlist = any(self.is_playlist_url(u) for u in filtered_urls)
        worker = YtdlpRunner(item_id, filtered_urls, settings, allow_playlist)
        worker.log.connect(self.on_log)
        worker.error.connect(self.on_error)
        worker.progress.connect(self.on_progress)
        worker.info.connect(self.on_info)
        worker.finished.connect(lambda: self.on_done(item_id))
        self._workers[item_id] = worker
        worker.start()

    def on_log(self, item_id: int, msg: str):
        print(msg)

    def on_error(self, item_id: int, msg: str):
        self._workers.pop(item_id, None)

        item = self._items.get(item_id)
        if not item:
            return
        log_path = self._write_error_log(item["title"], item_id, msg)
        item["error"] = msg
        item["log_path"] = log_path
        item["status"] = tr("downloads.status.failed")
        item["state"] = "error"
        item["updated_at"] = datetime.utcnow().isoformat()
        item["widget"].set_meta(tr("downloads.status.failed"))
        item["widget"].set_error(msg)
        self._save_list_csv()

    def on_done(self, item_id: int):
        self._workers.pop(item_id, None)

        item = self._items.get(item_id)
        if not item:
            return
        if item.get("state") == "error":
            return
        log_path = item.get("log_path", "")
        if log_path and os.path.exists(log_path):
            try:
                os.remove(log_path)
            except Exception:
                pass
        item["status"] = tr("downloads.status.done")
        item["state"] = "done"
        item["error"] = ""
        item["log_path"] = ""
        item["updated_at"] = datetime.utcnow().isoformat()
        item["widget"].set_meta(tr("downloads.status.done"))
        item["widget"].set_state("done")
        item["widget"].set_error("")
        self._save_list_csv()

    def on_progress(self, item_id: int, status: str, percent: float, eta: str, speed: str):
        item = self._items.get(item_id)
        if not item:
            return
        ansi = re.compile(r"\x1b\[[0-9;]*m")
        status = ansi.sub("", status or "")
        eta = ansi.sub("", eta or "")
        speed = ansi.sub("", speed or "")
        parts = []
        if status:
            parts.append(status)
        parts.append(f"{percent:.1f}%")
        if eta:
            parts.append(f"ETA {eta}")
        if speed:
            parts.append(f"@ {speed}")
        meta = "  ·  ".join(parts).strip()
        item["status"] = meta
        item["state"] = "running"
        item["updated_at"] = datetime.utcnow().isoformat()
        item["widget"].set_meta(meta)
        item["widget"].set_state("running")
        item["widget"].set_progress(percent)
        self._save_list_csv()

    def on_info(self, item_id: int, info: dict):
        item = self._items.get(item_id)
        if not item or not info:
            return
        title = info.get("title") or item["title"]
        uploader = info.get("uploader") or ""
        vid = info.get("id") or ""
        display = title
        if uploader:
            display = f"[{uploader}] {title}"
        item["title"] = display
        item["widget"].title_lbl.setText(display)
        self._save_list_csv()
        thumb_url, thumb_id = self._pick_thumbnail(info)
        if thumb_url:
            self._load_thumbnail(item_id, thumb_url, thumb_id)

    def on_clipboard_toggle(self, checked: bool):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if checked:
            clipboard.dataChanged.connect(self.on_clipboard_change)
        else:
            try:
                clipboard.dataChanged.disconnect(self.on_clipboard_change)
            except Exception:
                pass
        self._settings.clipboard_enabled = checked
        SettingsStore.save(self._settings)

    def on_clipboard_change(self):
        from PySide6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        urls = [self.normalize_youtube_url(u) for u in self.parse_urls(text)]
        for url in urls:
            vid = self.extract_video_id(url)
            if vid and vid in self._seen_clipboard:
                continue
            if vid:
                self._seen_clipboard.add(vid)
            self.run_ytdlp([url])

    def _show_menu(self, item_id: int, global_pos):
        item = self._items.get(item_id)
        if not item:
            return
        menu = QMenu(self)
        copy_link = menu.addAction(tr("downloads.menu.copy_link"))
        restart = menu.addAction(tr("downloads.menu.restart"))
        restart_incomplete = menu.addAction(tr("downloads.menu.restart_incomplete"))
        remove_completed = menu.addAction(tr("downloads.menu.remove_completed"))
        delete_item = menu.addAction(tr("downloads.menu.delete_item"))
        menu.addSeparator()
        lock_act = menu.addAction(tr("downloads.menu.lock"))
        lock_act.setCheckable(True)
        lock_act.setChecked(item.get("locked", False))
        action = menu.exec(global_pos)
        if action == copy_link:
            self._copy_links(item_id)
        elif action == restart:
            self._restart_item(item_id)
        elif action == restart_incomplete:
            self._restart_incomplete()
        elif action == remove_completed:
            self._remove_completed()
        elif action == delete_item:
            self._delete_item(item_id)
        elif action == lock_act:
            item["locked"] = lock_act.isChecked()
            item["updated_at"] = datetime.utcnow().isoformat()
            self._save_list_csv()


    def _copy_links(self, item_id: int):
        from PySide6.QtWidgets import QApplication
        item = self._items.get(item_id)
        if not item:
            return
        text = "\n".join(item.get("urls") or [])
        QApplication.clipboard().setText(text)

    def _restart_item(self, item_id: int):
        item = self._items.get(item_id)
        if not item or item.get("locked"):
            return
        urls = [self.normalize_youtube_url(u) for u in (item.get("urls") or [])]
        if not urls:
            return
        item["status"] = tr("downloads.status.queued")
        item["state"] = "queued"
        item["error"] = ""
        item["log_path"] = ""
        item["updated_at"] = datetime.utcnow().isoformat()
        item["widget"].set_meta(tr("downloads.status.queued"))
        item["widget"].set_error("")
        self._save_list_csv()
        self._start_worker_for_item(item_id, urls)

    def _restart_incomplete(self):
        for item_id, item in list(self._items.items()):
            if item.get("locked"):
                continue
            if item.get("state") in ("done",):
                continue
            self._restart_item(item_id)

    def _remove_completed(self):
        for item_id, item in list(self._items.items()):
            if item.get("locked"):
                continue
            if item.get("state") != "done":
                continue
            widget = item.get("widget")
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            self._items.pop(item_id, None)
        self._save_list_csv()
        self._reorder_items()

    def _delete_item(self, item_id: int):
        item = self._items.get(item_id)
        if not item or item.get("locked"):
            return
        worker = self._workers.get(item_id)
        if worker is not None:
            worker.cancel()
            worker.wait(2000)
            self._workers.pop(item_id, None)
        widget = item.get("widget")
        if widget:
            widget.setParent(None)
            widget.deleteLater()
        self._items.pop(item_id, None)
        self._save_list_csv()
        self._reorder_items()

    def _start_worker_for_item(self, item_id: int, urls):
        settings = SettingsStore.load()
        allow_playlist = any(self.is_playlist_url(u) for u in urls)
        worker = YtdlpRunner(item_id, urls, settings, allow_playlist)
        worker.log.connect(self.on_log)
        worker.error.connect(self.on_error)
        worker.progress.connect(self.on_progress)
        worker.finished.connect(lambda: self.on_done(item_id))
        self._workers[item_id] = worker
        worker.start()

    def _write_error_log(self, title: str, item_id: int, text: str):
        safe = re.sub(r"[^0-9A-Za-z._\-가-힣 ]+", "_", title).strip()
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"ERROR_{safe}({item_id})_{ts}.log"
        base_dir = self._app_dir()
        path = os.path.join(base_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            return ""
        return path

    def _save_list_csv(self):
        base_dir = self._app_dir()
        path = os.path.join(base_dir, "list.csv")
        rows = []
        for item in self._items.values():
            rows.append({
                "id": item["id"],
                "title": item["title"],
                "status": item["status"],
                "state": item.get("state", ""),
                "locked": item.get("locked", False),
                "urls": "|".join(item.get("urls") or []),
                "error": item.get("error", ""),
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
                "log_path": item["log_path"],
                "thumb_path": item.get("thumb_path", ""),
            })
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=list(rows[0].keys()) if rows else [
                        "id","title","status","state","locked","urls","error","created_at","updated_at","log_path","thumb_path"
                    ],
                )
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
        except Exception:
            pass

    def _load_list_csv(self):
        base_dir = self._app_dir()
        path = os.path.join(base_dir, "list.csv")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                rows.sort(key=lambda r: r.get("created_at", ""), reverse=self._sort_desc)
                for row in rows:
                    try:
                        item_id = int(row.get("id", 0))
                    except Exception:
                        continue
                    urls_raw = [u for u in row.get("urls", "").split("|") if u]
                    urls = [self.normalize_youtube_url(u) for u in urls_raw]
                    title = row.get("title", "")
                    status = row.get("status", "")
                    status = self._localize_status(status)
                    state = row.get("state", "")
                    locked = str(row.get("locked", "")).lower() in ("1","true","yes","on")
                    log_path = row.get("log_path", "")
                    thumb_path = row.get("thumb_path", "")
                    created_at = row.get("created_at") or datetime.utcnow().isoformat()
                    item_id = self.add_item(
                        title,
                        status,
                        row.get("error", ""),
                        urls=urls,
                        item_id=item_id,
                        state=state,
                        locked=locked,
                        log_path=log_path,
                    )
                    self._items[item_id]["created_at"] = created_at
                    self._items[item_id]["updated_at"] = row.get("updated_at") or created_at
                    if thumb_path and os.path.exists(thumb_path):
                        pix = QPixmap(thumb_path)
                        self._items[item_id]["widget"].set_thumbnail(pix)
                        self._items[item_id]["thumb_path"] = thumb_path
        except Exception:
            pass
        self._reorder_items()

    def _load_thumbnail(self, item_id: int, url: str, thumb_id: str = ""):
        item = self._items.get(item_id)
        if not item:
            return
        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return
            pix = QPixmap()
            pix.loadFromData(r.content)
            item["widget"].set_thumbnail(pix)
            self._thumb_dir = self._get_thumb_dir()
            os.makedirs(self._thumb_dir, exist_ok=True)
            name = thumb_id or str(item_id)
            safe = re.sub(r"[^0-9A-Za-z._\-]+", "_", name)
            thumb_path = os.path.join(self._thumb_dir, f"{safe}.jpg")
            with open(thumb_path, "wb") as f:
                f.write(r.content)
            item["thumb_path"] = thumb_path
            item["updated_at"] = datetime.utcnow().isoformat()
            self._save_list_csv()
        except Exception:
            pass

    def _app_dir(self):
        import sys
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(sys.argv[0]))

    def _base_dir(self):
        app_dir = self._app_dir()
        if os.path.basename(app_dir).lower() == "src":
            return os.path.dirname(app_dir)
        return app_dir

    def _get_download_dir(self):
        s = SettingsStore.load()
        base = s.download_dir or "ytdl"
        if os.path.isabs(base):
            return base
        return os.path.join(self._base_dir(), base)

    def _get_thumb_dir(self):
        return os.path.join(self._get_download_dir(), ".thumbnails")

    def _pick_thumbnail(self, info: dict):
        if info.get("_type") in ("playlist", "multi_video") or isinstance(info.get("entries"), list):
            entries = info.get("entries") or []
            for ent in entries:
                if not ent:
                    continue
                if isinstance(ent, dict):
                    thumb = ent.get("thumbnail")
                    vid = ent.get("id")
                    if thumb:
                        return thumb, (vid or "")
        return info.get("thumbnail"), (info.get("id") or "")

    def toggle_sort(self):
        self._sort_desc = not self._sort_desc
        self._settings.list_sort_desc = self._sort_desc
        SettingsStore.save(self._settings)
        self._update_sort_button()
        self._reorder_items()

    def _update_sort_button(self):
        self.sort_btn.setText(tr("downloads.sort_latest") if self._sort_desc else tr("downloads.sort_oldest"))

    def _reorder_items(self):
        widgets = []
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                widgets.append(w)

        items = list(self._items.values())
        items.sort(key=lambda x: x.get("created_at", ""), reverse=self._sort_desc)
        for item in items:
            self.content_layout.insertWidget(self.content_layout.count(), item["widget"])

    def retranslate(self):
        self.url_input.setPlaceholderText(tr("downloads.url_placeholder"))
        self.clipboard_toggle.setText(tr("downloads.clipboard"))
        self.clipboard_toggle.setToolTip(tr("downloads.clipboard_tooltip"))
        self.download_btn.setText(tr("downloads.download_button"))
        self._update_sort_button()
        for item in self._items.values():
            widget = item.get("widget")
            if widget is not None:
                widget.err_btn.setText(tr("downloads.error_button"))
            status = item.get("status", "")
            localized = self._localize_status(status)
            if localized != status:
                item["status"] = localized
                item["widget"].set_meta(localized)

    def _localize_status(self, status: str) -> str:
        if not status:
            return status
        normalized = status.strip().lower()
        mapping = {
            "queued": tr("downloads.status.queued"),
            "대기": tr("downloads.status.queued"),
            "대기중": tr("downloads.status.queued"),
            "queued": tr("downloads.status.queued"),
            "waiting": tr("downloads.status.queued"),
            "待機中": tr("downloads.status.queued"),
            "等待中": tr("downloads.status.queued"),
            "排队中": tr("downloads.status.queued"),
            "done": tr("downloads.status.done"),
            "완료": tr("downloads.status.done"),
            "完了": tr("downloads.status.done"),
            "完成": tr("downloads.status.done"),
            "failed": tr("downloads.status.failed"),
            "실패": tr("downloads.status.failed"),
            "失敗": tr("downloads.status.failed"),
            "失败": tr("downloads.status.failed"),
        }
        return mapping.get(normalized, status)
