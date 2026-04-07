"""
Intent Extractor -- sends messages to WorkLens API server for analysis.

PRIVACY:
  - Message text sent to WorkLens API (HTTPS), analyzed, then discarded
  - Text is NEVER stored on the server -- only JSON intent returned
  - OpenAI key lives on the server only, never exposed to clients
  - Voice audio: downloaded locally, sent to server as base64, deleted immediately
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WORKLENS_API_URL = "https://web-production-3c1ef.up.railway.app"
WORKLENS_TOKEN   = "wl_t-oYEjaAUaHGB0dpaNidVE6QyP7SwWuL"


class IntentExtractor:
    """Analyzes messages via WorkLens API. Never stores input content."""

    def extract_intent(self, text: str) -> dict:
        """
        Send text to WorkLens API, get structured intent JSON.
        Text is NOT stored after this call returns.
        """
        if not text or not text.strip():
            return self._empty()
        try:
            import requests
            resp = requests.post(
                f"{WORKLENS_API_URL}/analyze",
                json={
                    "text":   text.strip()[:2000],
                    "token":  WORKLENS_TOKEN,
                    "source": "telegram"
                },
                timeout=35
            )
            if resp.status_code == 401:
                logger.error("WorkLens API: invalid token")
                return self._empty()
            if resp.status_code == 429:
                logger.warning("WorkLens API: rate limit")
                return self._empty()
            if resp.status_code != 200:
                logger.error(f"WorkLens API error: {resp.status_code}")
                return self._empty()

            data = resp.json()
            if not data.get("ok"):
                logger.warning(f"Intent error: {data}")
                return self._empty()

            return data.get("intent", self._empty())

        except Exception as e:
            logger.error(f"Intent extraction failed: {e}")
            return self._empty()

    def transcribe_voice(self, audio_path: str) -> Optional[str]:
        """
        Transcribe voice via WorkLens API (Whisper server-side).
        Audio file deleted locally after sending.
        """
        path = Path(audio_path)
        try:
            if not path.exists():
                return None
            import requests, base64
            audio_b64 = base64.b64encode(path.read_bytes()).decode()
            resp = requests.post(
                f"{WORKLENS_API_URL}/transcribe",
                json={"audio_b64": audio_b64, "token": WORKLENS_TOKEN},
                timeout=60
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                return resp.json().get("transcript", "")
            return None
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None
        finally:
            path.unlink(missing_ok=True)
            logger.debug(f"Deleted audio: {path.name}")

    def _empty(self) -> dict:
        return {
            "has_task": False, "has_deadline": False, "deadline_text": None,
            "has_agreement": False, "has_question": False,
            "action_required": False, "urgency": "low", "has_file_request": False
        }
