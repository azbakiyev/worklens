"""
Intent Extractor -- calls WorkLens backend (extella) to analyze messages.

PRIVACY:
  - Message text sent to WorkLens server for analysis
  - Text is NOT stored on the server -- only JSON intent returned
  - OpenAI key stored server-side, never exposed to client
  - Voice audio transcribed via Whisper, then immediately deleted locally
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WORKLENS_API_URL = "https://api.extella.ai"
WORKLENS_EXPERT  = "worklens_analyze_intent"
WORKLENS_TOKEN   = "9060ee04-9506-4641-b461-d6c5d8713589"  # extella API token
CLIENT_TOKEN     = "wl_9060ee04-9506-4641-b461-d6c5d8713589"  # WorkLens client token


class IntentExtractor:
    """Analyzes message text via WorkLens backend. Never stores input content."""

    def extract_intent(self, text: str) -> dict:
        """
        Send text to WorkLens backend, get structured intent.
        Text is NOT stored after this call returns.
        """
        if not text or not text.strip():
            return self._empty()
        try:
            import requests
            resp = requests.post(
                f"{WORKLENS_API_URL}/api/expert/run",
                headers={
                    "X-Auth-Token": WORKLENS_TOKEN,
                    "Content-Type": "application/json"
                },
                json={
                    "expert_name": WORKLENS_EXPERT,
                    "params": {
                        "text": text[:2000],
                        "client_token": CLIENT_TOKEN,
                        "source": "telegram"
                    }
                },
                timeout=35
            )
            if resp.status_code != 200:
                logger.error(f"WorkLens API error: {resp.status_code}")
                return self._empty()

            data = resp.json()
            result = data.get("result", {})
            if isinstance(result, str):
                import json as _json
                result = _json.loads(result)

            if not result.get("ok"):
                logger.warning(f"Intent error: {result.get('error')}")
                return self._empty()

            return result.get("intent", self._empty())

        except Exception as e:
            logger.error(f"Intent extraction failed: {e}")
            return self._empty()

    def transcribe_voice(self, audio_path: str) -> Optional[str]:
        """
        Transcribe voice message via Whisper API (server-side).
        Audio file is deleted after transcription.
        """
        path = Path(audio_path)
        try:
            if not path.exists():
                return None
            import requests
            with open(path, "rb") as f:
                resp = requests.post(
                    f"{WORKLENS_API_URL}/api/expert/run",
                    headers={"X-Auth-Token": WORKLENS_TOKEN},
                    json={
                        "expert_name": "worklens_transcribe_voice",
                        "params": {
                            "client_token": CLIENT_TOKEN,
                            "audio_b64": __import__('base64').b64encode(f.read()).decode()
                        }
                    },
                    timeout=60
                )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("transcript", "")
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
            "has_agreement": False, "has_question": False, "action_required": False,
            "urgency": "low", "has_file_request": False
        }
