from PySide6.QtCore import QThread, Signal
import traceback
import os

class YtdlpRunner(QThread):
    log = Signal(int, str)
    error = Signal(int, str)
    progress = Signal(int, str, float, str, str)
    info = Signal(int, dict)

    def __init__(self, item_id: int, urls, settings, allow_playlist: bool):
        super().__init__()
        self.item_id = item_id
        self.urls = urls
        self.settings = settings
        self.allow_playlist = allow_playlist

    def run(self):
        try:
            import yt_dlp
        except Exception as e:
            self.error.emit(self.item_id, f"yt-dlp import failed: {e}")
            return

        opts = self._build_options()
        max_attempts = getattr(self.settings, "max_attempts", 1)
        try:
            max_attempts = int(max_attempts)
        except Exception:
            max_attempts = 1
        max_attempts = max(1, max_attempts)
        opts["progress_hooks"] = [self._progress_hook]
        opts["quiet"] = True
        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    for url in self.urls:
                        try:
                            info = ydl.extract_info(url, download=False)
                            self.info.emit(self.item_id, info or {})
                        except Exception:
                            pass
                    ydl.download(self.urls)
                last_err = None
                break
            except Exception:
                last_err = traceback.format_exc()
                if attempt < max_attempts:
                    self.log.emit(self.item_id, f"Retrying download ({attempt}/{max_attempts})")
                    continue
                break
        if last_err:
            self.error.emit(self.item_id, last_err)

    def _progress_hook(self, d):
        status = d.get("status", "")
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes") or 0
        if total:
            pct = (downloaded / total) * 100.0
        else:
            pct = None
        eta = d.get("_eta_str", "")
        speed = d.get("_speed_str", "")
        if pct is None:
            try:
                percent = d.get("_percent_str", "0.0%")
                pct = float(percent.strip("%"))
            except Exception:
                pct = 0.0
        self.progress.emit(self.item_id, status, float(pct), eta, speed)

    def _build_options(self):
        s = self.settings
        download_dir = getattr(s, "download_dir", "")
        if download_dir and not os.path.isabs(download_dir):
            base = os.path.dirname(os.path.abspath(__file__))
            base = os.path.dirname(base)  # src
            base = os.path.dirname(base)  # project root
            download_dir = os.path.join(base, download_dir)
        outtmpl_default = getattr(s, "outtmpl_default", "")
        outtmpl_playlist = getattr(s, "outtmpl_playlist", "")
        outtmpl = outtmpl_playlist if self.allow_playlist else outtmpl_default
        opts = {
            "noplaylist": not self.allow_playlist,
            "paths": {"home": download_dir},
            "outtmpl": outtmpl,
            "format": (getattr(s, "format_selector", None) or None),
            "merge_output_format": (getattr(s, "merge_output_format", None) or None),
            "concurrent_fragment_downloads": getattr(s, "concurrent_fragments", 4),
            "writesubtitles": getattr(s, "write_subs", False),
            "writeautomaticsub": getattr(s, "write_auto_subs", False),
            "subtitleslangs": [x.strip() for x in getattr(s, "sub_langs", "").split(',') if x.strip()],
            "embedsubtitles": getattr(s, "embed_subs", False),
            "writethumbnail": getattr(s, "write_thumbnail", False),
            "embedthumbnail": getattr(s, "embed_thumbnail", False),
            "addmetadata": getattr(s, "add_metadata", False),
            "cookiesfrombrowser": getattr(s, "cookies_from_browser", None) if getattr(s, "use_cookies_from_browser", False) else None,
            "cookiefile": (getattr(s, "cookies_file", None) or None),
            "username": (getattr(s, "username", None) or None),
            "password": (getattr(s, "password", None) or None),
            "usenetrc": getattr(s, "use_netrc", False),
            "proxy": (getattr(s, "proxy", None) or None),
            "user_agent": (getattr(s, "user_agent", None) or None),
            "http_headers": self._parse_headers(getattr(s, "extra_headers", "")),
            "ratelimit": (getattr(s, "rate_limit", None) or None),
            "retries": getattr(s, "retries", 10),
            "no_check_certificate": getattr(s, "no_check_certificate", False),
            "geo_bypass_country": (getattr(s, "geo_bypass_country", None) or None),
            "extractor_args": {
                "youtube": {
                    "player_client": [x.strip() for x in getattr(s, "yt_player_clients", "").split(',') if x.strip()],
                    "lang": [getattr(s, "yt_lang", "")] if getattr(s, "yt_lang", "") else [],
                }
            },
        }
        if getattr(s, "yt_skip_age_restricted", False):
            opts["match_filter"] = "age_limit is None or age_limit < 18"

        if getattr(s, "sponsorblock_enable", False):
            sb_remove = getattr(s, "sponsorblock_remove", "")
            sb_mark = getattr(s, "sponsorblock_mark", "")
            sb_api = getattr(s, "sponsorblock_api_url", "")
            if sb_remove:
                opts["sponsorblock_remove"] = [x.strip() for x in sb_remove.split(',') if x.strip()]
            if sb_mark:
                opts["sponsorblock_mark"] = [x.strip() for x in sb_mark.split(',') if x.strip()]
            if sb_api:
                opts["sponsorblock_api"] = sb_api

        return {k: v for k, v in opts.items() if v is not None}

    @staticmethod
    def _parse_headers(text: str):
        headers = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
        return headers
