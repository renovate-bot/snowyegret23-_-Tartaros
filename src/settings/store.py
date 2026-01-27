from configparser import ConfigParser
from dataclasses import dataclass, asdict
from typing import Dict, Any
import os
import sys


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.ini")


@dataclass
class AppSettings:
    language: str = "English"
    download_dir: str = "ytdl"

    outtmpl_default: str = "[%(uploader)s] %(title)s (%(id)s).%(ext)s"
    outtmpl_playlist: str = "[Playlist] %(playlist_title)s/%(playlist_index)03d. %(title)s (%(id)s).%(ext)s"
    output_format: str = "mp4"
    video_quality: str = "best"
    audio_quality: str = "best"
    concurrent_fragments: int = 4
    verify_download: bool = True
    prefer_largest_file: bool = False

    write_subs: bool = False
    write_auto_subs: bool = False
    sub_langs: str = "ko,en"
    embed_subs: bool = False
    write_thumbnail: bool = False
    embed_thumbnail: bool = True
    embed_chapters: bool = True
    add_metadata: bool = True

    cookies_from_browser: str = "chrome"
    cookies_file: str = ""
    cookies_text: str = ""
    use_cookies_from_browser: bool = False
    enable_age_restricted: bool = False

    proxy: str = ""
    retries: int = 10
    concurrent_downloads: int = 3

    yt_player_clients: str = ""
    yt_lang: str = "ko"
    yt_remote_components: str = "ejs:github"
    yt_po_token: str = ""
    deno_path: str = ""
    ffmpeg_path: str = ""

    sponsorblock_enable: bool = False
    sponsorblock_remove: str = "sponsor,intro,outro"
    sponsorblock_mark: str = ""

    window_x: int = 100
    window_y: int = 100
    window_w: int = 900
    window_h: int = 640
    settings_x: int = 120
    settings_y: int = 120
    settings_w: int = 900
    settings_h: int = 640
    list_sort_desc: bool = False
    clipboard_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppSettings":
        obj = cls()
        for k, v in data.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj


class SettingsStore:
    @staticmethod
    def _app_dir() -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(sys.argv[0]))

    @staticmethod
    def write_cookies_text(text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        path = os.path.join(SettingsStore._app_dir(), "cookies.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            return ""
        return path

    @staticmethod
    def load() -> AppSettings:
        if not os.path.exists(SETTINGS_FILE):
            return AppSettings()
        cfg = ConfigParser(interpolation=None)
        try:
            cfg.read(SETTINGS_FILE, encoding="utf-8")
        except Exception:
            return AppSettings()
        data = {}
        for section in cfg.sections():
            for key, value in cfg.items(section):
                data[key] = value
        int_keys = {
            "concurrent_fragments", "retries", "concurrent_downloads",
            "window_x", "window_y", "window_w", "window_h",
            "settings_x", "settings_y", "settings_w", "settings_h"
        }
        bool_keys = {
            "write_subs", "write_auto_subs", "embed_subs", "write_thumbnail",
            "embed_thumbnail", "embed_chapters", "add_metadata", "use_cookies_from_browser",
            "enable_age_restricted", "verify_download", "prefer_largest_file",
            "sponsorblock_enable", "list_sort_desc", "clipboard_enabled"
        }
        for key in list(data.keys()):
            if key in int_keys:
                try:
                    data[key] = int(data[key])
                except Exception:
                    pass
            if key in bool_keys:
                data[key] = str(data[key]).lower() in ("1", "true", "yes", "on")
        return AppSettings.from_dict(data)

    @staticmethod
    def save(settings: AppSettings) -> None:
        cfg = ConfigParser(interpolation=None)
        cfg["general"] = {
            "language": settings.language,
            "download_dir": settings.download_dir,
        }
        cfg["output"] = {
            "outtmpl_default": settings.outtmpl_default,
            "outtmpl_playlist": settings.outtmpl_playlist,
            "output_format": settings.output_format,
            "video_quality": settings.video_quality,
            "audio_quality": settings.audio_quality,
            "concurrent_fragments": str(settings.concurrent_fragments),
            "verify_download": str(settings.verify_download),
            "prefer_largest_file": str(settings.prefer_largest_file),
        }
        cfg["subs_meta"] = {
            "write_subs": str(settings.write_subs),
            "write_auto_subs": str(settings.write_auto_subs),
            "sub_langs": settings.sub_langs,
            "embed_subs": str(settings.embed_subs),
            "write_thumbnail": str(settings.write_thumbnail),
            "embed_thumbnail": str(settings.embed_thumbnail),
            "embed_chapters": str(settings.embed_chapters),
            "add_metadata": str(settings.add_metadata),
        }
        cfg["auth"] = {
            "use_cookies_from_browser": str(settings.use_cookies_from_browser),
            "cookies_from_browser": settings.cookies_from_browser,
            "cookies_file": settings.cookies_file,
            "cookies_text": settings.cookies_text,
            "enable_age_restricted": str(settings.enable_age_restricted),
        }
        cfg["network"] = {
            "proxy": settings.proxy,
            "retries": str(settings.retries),
            "concurrent_downloads": str(settings.concurrent_downloads),
        }
        cfg["youtube"] = {
            "yt_player_clients": settings.yt_player_clients,
            "yt_lang": settings.yt_lang,
            "yt_remote_components": settings.yt_remote_components,
            "yt_po_token": settings.yt_po_token,
            "deno_path": settings.deno_path,
            "ffmpeg_path": settings.ffmpeg_path,
        }
        cfg["sponsorblock"] = {
            "sponsorblock_enable": str(settings.sponsorblock_enable),
            "sponsorblock_remove": settings.sponsorblock_remove,
            "sponsorblock_mark": settings.sponsorblock_mark,
        }
        cfg["ui"] = {
            "window_x": str(settings.window_x),
            "window_y": str(settings.window_y),
            "window_w": str(settings.window_w),
            "window_h": str(settings.window_h),
            "settings_x": str(settings.settings_x),
            "settings_y": str(settings.settings_y),
            "settings_w": str(settings.settings_w),
            "settings_h": str(settings.settings_h),
            "list_sort_desc": str(settings.list_sort_desc),
            "clipboard_enabled": str(settings.clipboard_enabled),
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)
