"""
Capture Module — monitors active application and window metadata.
Works on macOS, Windows, and Linux.

What we capture (every 5 sec):
  - Active application name
  - Application category (spreadsheet, browser, email, etc.)
  - Clipboard data TYPE only (never the content itself)
  - Activity level estimate

What we NEVER capture:
  - Keystrokes or passwords
  - Document/email content
  - Screenshots (not stored)
  - Personal messages
"""
import logging
import platform
import threading
import time
import uuid
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

SYSTEM = platform.system()  # Darwin / Windows / Linux

# ---------------------------------------------------------------------------
# App → category mapping
# ---------------------------------------------------------------------------
APP_CATEGORIES: dict[str, str] = {
    "microsoft excel": "spreadsheet",
    "numbers": "spreadsheet",
    "google sheets": "spreadsheet",
    "libreoffice calc": "spreadsheet",
    "microsoft word": "document",
    "pages": "document",
    "google docs": "document",
    "libreoffice writer": "document",
    "microsoft outlook": "email",
    "apple mail": "email",
    "mail": "email",
    "thunderbird": "email",
    "google chrome": "browser",
    "safari": "browser",
    "firefox": "browser",
    "microsoft edge": "browser",
    "arc": "browser",
    "yandex": "browser",
    "telegram": "messenger",
    "whatsapp": "messenger",
    "slack": "messenger",
    "discord": "messenger",
    "zoom": "video_call",
    "microsoft teams": "video_call",
    "facetime": "video_call",
    "salesforce": "crm",
    "hubspot": "crm",
    "1с": "erp",
    "1c": "erp",
    "visual studio code": "ide",
    "pycharm": "ide",
    "xcode": "ide",
    "cursor": "ide",
    "adobe acrobat": "pdf",
    "preview": "pdf",
    "finder": "file_manager",
    "explorer": "file_manager",
    "terminal": "terminal",
    "iterm2": "terminal",
    "warp": "terminal",
    "extella": "ai_platform",
    "claude": "ai_platform",
    "chatgpt": "ai_platform",
}

# Apps that trigger auto-pause (privacy protection)
PRIVACY_APPS: set[str] = {
    "1password",
    "keychain access",
    "lastpass",
    "bitwarden",
    "system preferences",
    "system settings",
}

# Raw SQL INSERT — avoids all ORM session lifecycle issues
_INSERT_EVENT = text("""
    INSERT INTO activity_events
        (timestamp, app_name, window_category, activity_level,
         clipboard_type, input_method, session_id, is_privacy_zone)
    VALUES
        (:ts, :app_name, :window_category, :activity_level,
         :clipboard_type, :input_method, :session_id, :is_privacy_zone)
""")


# ---------------------------------------------------------------------------
# Platform-specific active app detection
# ---------------------------------------------------------------------------

def _get_active_app_macos() -> Tuple[str, str]:
    """Return (app_name, window_title) on macOS via osascript."""
    import subprocess
    script = (
        'tell application "System Events"\n'
        '    set frontApp to first application process whose frontmost is true\n'
        '    set appName to name of frontApp\n'
        'end tell\n'
        'return appName'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=3
        )
        app_name = result.stdout.strip() if result.returncode == 0 else "Unknown"
        return app_name, ""
    except Exception as e:
        logger.debug(f"macOS app detection failed: {e}")
        return "Unknown", ""


def _get_active_app_windows() -> Tuple[str, str]:
    """Return (app_name, window_title) on Windows."""
    try:
        import win32gui
        import win32process
        import psutil
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return proc.name().replace(".exe", ""), title
    except Exception as e:
        logger.debug(f"Windows app detection failed: {e}")
        return "Unknown", ""


def _get_active_app_linux() -> Tuple[str, str]:
    """Return (app_name, window_title) on Linux via xdotool."""
    import subprocess
    try:
        result = subprocess.run(
            ["xdotool", "getwindowfocus", "getwindowname"],
            capture_output=True, text=True, timeout=3
        )
        title = result.stdout.strip() if result.returncode == 0 else ""
        app = title.split(" - ")[-1] if " - " in title else title
        return app, title
    except Exception as e:
        logger.debug(f"Linux app detection failed: {e}")
        return "Unknown", ""


def get_active_app() -> Tuple[str, str]:
    """Platform-agnostic active application detection."""
    if SYSTEM == "Darwin":
        return _get_active_app_macos()
    elif SYSTEM == "Windows":
        return _get_active_app_windows()
    else:
        return _get_active_app_linux()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def categorize_app(app_name: str) -> str:
    """Map application name to a human-readable category."""
    name_lower = app_name.lower()
    for key, category in APP_CATEGORIES.items():
        if key in name_lower:
            return category
    return "other"


def is_privacy_zone(app_name: str) -> bool:
    """Return True if the app should trigger capture pause."""
    return app_name.lower() in PRIVACY_APPS


def get_clipboard_type() -> str:
    """
    Detect the TYPE of data in the clipboard without reading or storing the content.
    Returns: empty / tabular / number / email / url / short_text / text / unknown
    """
    try:
        import pyperclip
        content = pyperclip.paste()
        if not content:
            return "empty"
        stripped = content.strip()
        if "\t" in stripped:
            return "tabular"
        try:
            float(stripped.replace(",", ".").replace(" ", ""))
            return "number"
        except ValueError:
            pass
        if "@" in stripped and "." in stripped and len(stripped) < 100 and " " not in stripped:
            return "email"
        if stripped.startswith(("http://", "https://", "ftp://")):
            return "url"
        if len(stripped) < 80:
            return "short_text"
        return "text"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Main capture engine
# ---------------------------------------------------------------------------

class ActivityCapture:
    """
    Polls the active application every `interval` seconds.
    Saves structured ActivityEvent records to the local database.
    Never stores document content, keystrokes, or personal data.
    """

    def __init__(self, db_manager, interval: float = 5.0) -> None:
        self.db = db_manager
        self.interval = interval
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._session_id: str = str(uuid.uuid4())

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start capture in a background daemon thread."""
        if self._running:
            logger.warning("Capture already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="WorkLens-Capture"
        )
        self._thread.start()
        logger.info(f"Capture started | session={self._session_id} | interval={self.interval}s")

    def stop(self) -> None:
        """Stop the capture loop and wait for thread exit."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("Capture stopped")

    def pause(self) -> None:
        """Pause capture (e.g., user entered privacy zone manually)."""
        self._paused = True
        logger.info("Capture paused")

    def resume(self) -> None:
        """Resume capture after pause."""
        self._paused = False
        logger.info("Capture resumed")

    def _capture_loop(self) -> None:
        """Background thread: poll active app, save to DB."""
        while self._running:
            try:
                if not self._paused:
                    self._capture_once()
            except Exception as e:
                logger.error(f"Capture loop error: {e}")
            time.sleep(self.interval)

    def _capture_once(self) -> None:
        """Take a single activity snapshot and persist it via raw SQL.

        We use a raw SQL INSERT (not ORM) to avoid SQLAlchemy's session
        lifecycle issues (detached-instance / bhk3 error) in a
        multi-threaded background loop.
        """
        app_name, _ = get_active_app()

        if is_privacy_zone(app_name):
            logger.debug(f"Privacy zone: {app_name} — skipping")
            return

        category: str = categorize_app(app_name)
        clip_type: str = get_clipboard_type()

        params = {
            "ts": datetime.utcnow().isoformat(),
            "app_name": app_name,
            "window_category": category,
            "activity_level": "medium",
            "clipboard_type": clip_type,
            "input_method": "unknown",
            "session_id": self._session_id,
            "is_privacy_zone": 0,
        }

        with self.db.get_session() as session:
            session.execute(_INSERT_EVENT, params)

        logger.debug(f"[{app_name}] cat={category} clip={clip_type}")
