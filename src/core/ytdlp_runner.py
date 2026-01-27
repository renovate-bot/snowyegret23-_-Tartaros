from PySide6.QtCore import QThread, Signal
import traceback
import glob
import os
import sys


class DownloadCancelled(Exception):
    pass


class _YtdlpLogger:
    def __init__(self, runner: "YtdlpRunner", item_id: int):
        self._runner = runner
        self._item_id = item_id

    def debug(self, msg):
        if msg and msg.startswith("[debug]"):
            self._runner.log.emit(self._item_id, msg)

    def warning(self, msg):
        if msg:
            self._runner.log.emit(self._item_id, f"warn: {msg}")

    def error(self, msg):
        if msg:
            self._runner.log.emit(self._item_id, f"err: {msg}")


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
        self._cancelled = False
        self._download_dir = ""
        self._current_filename = ""

    def cancel(self):
        self._cancelled = True
        self.requestInterruption()

    def is_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def run(self):
        tool_paths = self._ensure_bundled_tools()
        try:
            import yt_dlp
        except Exception as e:
            self.error.emit(self.item_id, f"yt-dlp import failed: {e}")
            return

        opts = self._build_options()
        ffmpeg_path = getattr(self.settings, "ffmpeg_path", "").strip() or tool_paths.get("ffmpeg")
        if ffmpeg_path:
            opts["ffmpeg_location"] = ffmpeg_path
        self.log.emit(
            self.item_id,
            f"settings: output_format={getattr(self.settings, 'output_format', '')} "
            f"video_quality={getattr(self.settings, 'video_quality', '')} "
            f"audio_quality={getattr(self.settings, 'audio_quality', '')} "
            f"prefer_largest_file={getattr(self.settings, 'prefer_largest_file', False)}"
        )
        self.log.emit(self.item_id, f"format={opts.get('format')}")
        self.log.emit(self.item_id, f"merge_output_format={opts.get('merge_output_format')}")
        if ffmpeg_path:
            self.log.emit(self.item_id, f"ffmpeg_location={ffmpeg_path}")
        if opts.get("remote_components"):
            self.log.emit(self.item_id, f"remote_components={opts.get('remote_components')}")
        max_attempts = getattr(self.settings, "max_attempts", 1)
        try:
            max_attempts = int(max_attempts)
        except Exception:
            max_attempts = 1
        max_attempts = max(1, max_attempts)
        opts["progress_hooks"] = [self._progress_hook]
        opts["quiet"] = True
        opts["logger"] = _YtdlpLogger(self, self.item_id)
        self._download_dir = opts.get("paths", {}).get("home", "")

        last_err = None
        fallback_used = False
        cancelled = False
        for attempt in range(1, max_attempts + 1):
            if self.is_cancelled():
                cancelled = True
                break
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    for url in self.urls:
                        if self.is_cancelled():
                            cancelled = True
                            break
                        try:
                            info = ydl.extract_info(url, download=False)
                            self.info.emit(self.item_id, info or {})
                        except DownloadCancelled:
                            cancelled = True
                            break
                        except Exception:
                            pass
                    if cancelled:
                        break
                    ydl.download(self.urls)
                last_err = None
                break
            except DownloadCancelled:
                cancelled = True
                break
            except Exception:
                last_err = traceback.format_exc()
                if (not fallback_used) and ("Requested format is not available" in last_err):
                    output_format = getattr(self.settings, "output_format", "mp4")
                    opts["format"] = self._fallback_format_selector(output_format)
                    opts.pop("merge_output_format", None)
                    opts.pop("format_sort", None)
                    opts.pop("format_sort_force", None)
                    if "extractor_args" in opts and "youtube" in opts["extractor_args"]:
                        opts["extractor_args"]["youtube"].pop("player_client", None)
                    fallback_used = True
                    self.log.emit(self.item_id, "Fallback format: best")
                    try:
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            ydl.download(self.urls)
                        last_err = None
                        break
                    except DownloadCancelled:
                        cancelled = True
                        break
                    except Exception:
                        last_err = traceback.format_exc()
                if attempt < max_attempts:
                    self.log.emit(self.item_id, f"Retrying download ({attempt}/{max_attempts})")
                    continue
                break

        if cancelled:
            self._cleanup_temp_files()
            self.log.emit(self.item_id, "Download cancelled")
            return

        if last_err:
            self.error.emit(self.item_id, last_err)

    def _progress_hook(self, d):
        if self.is_cancelled():
            filename = d.get("filename", "")
            if filename:
                self._current_filename = filename
            raise DownloadCancelled("Download cancelled by user")

        status = d.get("status", "")
        filename = d.get("filename", "")
        if filename:
            self._current_filename = filename

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
            base = os.path.dirname(base)
            base = os.path.dirname(base)
            download_dir = os.path.join(base, download_dir)
        outtmpl_default = getattr(s, "outtmpl_default", "")
        outtmpl_playlist = getattr(s, "outtmpl_playlist", "")
        outtmpl = outtmpl_playlist if self.allow_playlist else outtmpl_default
        output_format = getattr(s, "output_format", "mp4")
        format_selector = getattr(s, "format_selector", "") or self._build_format_selector(output_format)
        merge_output_format = getattr(s, "merge_output_format", "") or (
            output_format if output_format in ("mp4", "mkv", "webm") else None
        )
        remote_components = getattr(s, "yt_remote_components", "")
        if isinstance(remote_components, str):
            remote_components = remote_components.strip()
            remote_components = [remote_components] if remote_components else None

        postprocessors = []
        embed_thumbnail = getattr(s, "embed_thumbnail", False)
        embed_subs = getattr(s, "embed_subs", False)
        embed_chapters = getattr(s, "embed_chapters", True)
        add_metadata = getattr(s, "add_metadata", False)

        if embed_subs:
            postprocessors.append({"key": "FFmpegEmbedSubtitle"})
        if embed_thumbnail:
            postprocessors.append({"key": "EmbedThumbnail"})
        if add_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_chapters": embed_chapters, "add_metadata": True})
        elif embed_chapters:
            postprocessors.append({"key": "FFmpegMetadata", "add_chapters": True, "add_metadata": False})

        cookies_browser = None
        if getattr(s, "use_cookies_from_browser", False):
            browser_name = getattr(s, "cookies_from_browser", "chrome")
            if browser_name:
                cookies_browser = (browser_name,)

        opts = {
            "noplaylist": not self.allow_playlist,
            "paths": {"home": download_dir},
            "outtmpl": outtmpl,
            "format": format_selector or None,
            "merge_output_format": merge_output_format,
            "concurrent_fragment_downloads": getattr(s, "concurrent_fragments", 4),
            "writesubtitles": getattr(s, "write_subs", False),
            "writeautomaticsub": getattr(s, "write_auto_subs", False),
            "subtitleslangs": [x.strip() for x in getattr(s, "sub_langs", "").split(',') if x.strip()] or None,
            "writethumbnail": getattr(s, "write_thumbnail", False) or embed_thumbnail,
            "cookiesfrombrowser": cookies_browser,
            "cookiefile": (getattr(s, "cookies_file", None) or None),
            "proxy": (getattr(s, "proxy", None) or None),
            "retries": getattr(s, "retries", 10),
            "extractor_args": {
                "youtube": {
                    "lang": [getattr(s, "yt_lang", "")] if getattr(s, "yt_lang", "") else [],
                }
            },
            "remote_components": remote_components,
            "postprocessors": postprocessors if postprocessors else None,
        }
        player_clients = [x.strip() for x in getattr(s, "yt_player_clients", "").split(',') if x.strip()]
        if player_clients:
            opts["extractor_args"]["youtube"]["player_client"] = player_clients
        if getattr(s, "prefer_largest_file", False):
            opts["format_sort"] = ["filesize:best", "res:best", "fps:best", "br:best"]
            opts["format_sort_force"] = True
        po_token = getattr(s, "yt_po_token", "")
        if po_token:
            opts["extractor_args"]["youtube"]["po_token"] = [po_token]
        if output_format in ("mp3", "m4a", "opus", "flac"):
            aq = getattr(s, "audio_quality", "best")
            aq_val = aq.replace("k", "") if isinstance(aq, str) else ""
            pp = {
                "key": "FFmpegExtractAudio",
                "preferredcodec": output_format,
            }
            if aq_val and aq_val.isdigit():
                pp["preferredquality"] = aq_val
            current_pp = opts.get("postprocessors") or []
            opts["postprocessors"] = [pp] + current_pp
        if getattr(s, "yt_skip_age_restricted", False):
            opts["match_filter"] = "age_limit is None or age_limit < 18"

        if getattr(s, "sponsorblock_enable", False):
            sb_remove = getattr(s, "sponsorblock_remove", "")
            sb_mark = getattr(s, "sponsorblock_mark", "")
            sb_api = getattr(s, "sponsorblock_api_url", "")
            categories = []
            if sb_remove:
                categories.extend([x.strip() for x in sb_remove.split(',') if x.strip()])
            if sb_mark:
                categories.extend([x.strip() for x in sb_mark.split(',') if x.strip()])
            if categories:
                sb_pp = {
                    "key": "SponsorBlock",
                    "categories": categories,
                }
                if sb_api:
                    sb_pp["api"] = sb_api
                current_pp = opts.get("postprocessors") or []
                opts["postprocessors"] = current_pp + [sb_pp]
                if sb_remove:
                    remove_cats = [x.strip() for x in sb_remove.split(',') if x.strip()]
                    modify_pp = {
                        "key": "ModifyChapters",
                        "remove_sponsor_segments": remove_cats,
                    }
                    opts["postprocessors"] = opts["postprocessors"] + [modify_pp]

        return {k: v for k, v in opts.items() if v is not None}

    def _build_format_selector(self, output_format: str) -> str:
        vq = getattr(self.settings, "video_quality", "best")
        audio_only = output_format in ("mp3", "m4a", "opus", "flac") or vq == "audio_only"
        if audio_only:
            return "bestaudio/best"
        def best_combo(limit: str = "") -> str:
            if output_format == "mp4":
                return (
                    f"bestvideo[ext=mp4]{limit}+bestaudio[ext=m4a]/"
                    f"bestvideo{limit}+bestaudio/best{limit}/best"
                )
            if output_format == "webm":
                return (
                    f"bestvideo[ext=webm]{limit}+bestaudio[ext=webm]/"
                    f"bestvideo{limit}+bestaudio/best{limit}/best"
                )
            return f"bestvideo{limit}+bestaudio/best{limit}/best"

        if vq == "best":
            return best_combo()
        if isinstance(vq, str) and vq.endswith("p"):
            try:
                height = int(vq[:-1])
            except Exception:
                height = None
            if height:
                return best_combo(f"[height<={height}]")
        return best_combo()

    @staticmethod
    def _fallback_format_selector(output_format: str) -> str:
        if output_format in ("mp3", "m4a", "opus", "flac"):
            return "bestaudio/best"
        return "best"

    def _cleanup_temp_files(self):
        patterns_to_clean = []

        if self._current_filename:
            base = self._current_filename
            patterns_to_clean.extend([
                f"{base}.part",
                f"{base}.part-Frag*",
                f"{base}.ytdl",
                f"{base}.temp",
            ])
            base_no_ext = os.path.splitext(base)[0]
            patterns_to_clean.extend([
                f"{base_no_ext}.*.part",
                f"{base_no_ext}.f*.mp4",
                f"{base_no_ext}.f*.webm",
                f"{base_no_ext}.f*.m4a",
            ])

        if self._download_dir and os.path.isdir(self._download_dir):
            patterns_to_clean.extend([
                os.path.join(self._download_dir, "*.part"),
                os.path.join(self._download_dir, "*.ytdl"),
                os.path.join(self._download_dir, "*.part-Frag*"),
            ])

        for pattern in patterns_to_clean:
            try:
                for f in glob.glob(pattern):
                    if os.path.isfile(f):
                        try:
                            os.remove(f)
                            self.log.emit(self.item_id, f"Cleaned up: {os.path.basename(f)}")
                        except Exception:
                            pass
            except Exception:
                pass

    @staticmethod
    def _parse_headers(text: str):
        headers = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
        return headers

    def _ensure_bundled_tools(self):
        found = {}
        for tool in ("deno.exe", "ffmpeg.exe"):
            candidates = []
            override = ""
            if tool == "deno.exe":
                override = getattr(self.settings, "deno_path", "").strip()
            elif tool == "ffmpeg.exe":
                override = getattr(self.settings, "ffmpeg_path", "").strip()
            if override and os.path.exists(override):
                candidates.append(override)
            if getattr(sys, "frozen", False):
                base = getattr(sys, "_MEIPASS", "")
                if base:
                    candidates.append(os.path.join(base, tool))
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), tool))
            bundle_dir = self._bundle_dir()
            if bundle_dir:
                candidates.append(os.path.join(bundle_dir, tool))
            for path in candidates:
                if os.path.exists(path):
                    tool_dir = os.path.dirname(path)
                    current = os.environ.get("PATH", "")
                    if tool_dir not in current.split(os.pathsep):
                        os.environ["PATH"] = tool_dir + os.pathsep + current
                    key = "deno" if tool.startswith("deno") else "ffmpeg"
                    found[key] = path
                    break
            if tool.startswith("ffmpeg") and "ffmpeg" not in found:
                deep = self._find_in_dir(bundle_dir, tool)
                if deep:
                    tool_dir = os.path.dirname(deep)
                    current = os.environ.get("PATH", "")
                    if tool_dir not in current.split(os.pathsep):
                        os.environ["PATH"] = tool_dir + os.pathsep + current
                    found["ffmpeg"] = deep
            if tool.startswith("deno") and "deno" not in found:
                deep = self._find_in_dir(bundle_dir, tool)
                if deep:
                    tool_dir = os.path.dirname(deep)
                    current = os.environ.get("PATH", "")
                    if tool_dir not in current.split(os.pathsep):
                        os.environ["PATH"] = tool_dir + os.pathsep + current
                    found["deno"] = deep
        return found

    @staticmethod
    def _bundle_dir():
        if getattr(sys, "frozen", False):
            return os.path.join(os.path.dirname(sys.executable), "bundle")
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(base)
        base = os.path.dirname(base)
        return os.path.join(base, "bundle")

    @staticmethod
    def _find_in_dir(root_dir: str, filename: str) -> str:
        if not root_dir or not os.path.exists(root_dir):
            return ""
        for root, _dirs, files in os.walk(root_dir):
            if filename in files:
                return os.path.join(root, filename)
        return ""
