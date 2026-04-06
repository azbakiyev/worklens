"""
Intent Extractor — analyzes message text and voice via OpenAI API.

PRIVACY CONTRACT:
  - Message text is sent to OpenAI API and immediately discarded after response
  - Voice audio is sent to Whisper API and the local file is deleted after
  - NO message content is ever written to disk or database
  - Only the extracted JSON intent structure is persisted
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a work assistant. Analyze the message and return ONLY valid JSON.
No explanations. No markdown. Just the JSON object.

JSON schema (all fields required):
{
  "has_task": bool,          // assigns a task or action item
  "has_deadline": bool,      // specific deadline mentioned
  "deadline_text": str|null, // deadline as mentioned or null
  "has_agreement": bool,     // parties agreed on something
  "has_question": bool,      // contains a question needing answer
  "action_required": bool,   // recipient needs to act
  "urgency": str,            // "low" | "medium" | "high"
  "has_file_request": bool   // requesting a file/document
}"""


class IntentExtractor:
    """Extracts structured intents from text. Never stores input content."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None

    def _client_(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def extract_intent(self, text: str) -> dict:
        """
        Send text to GPT-4o-mini, get structured intent.
        Input text is NOT stored after this call returns.
        """
        if not text or not text.strip():
            return self._empty()
        try:
            resp = self._client_().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text[:2000]},
                ],
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content)
            return self._validate(raw)
        except Exception as e:
            logger.error(f"Intent extraction failed: {e}")
            return self._empty()

    def transcribe_voice(self, audio_path: str) -> Optional[str]:
        """
        Transcribe voice message via Whisper API.
        Audio file is deleted after transcription regardless of outcome.
        Returns transcript text or None on failure.
        """
        path = Path(audio_path)
        try:
            if not path.exists():
                logger.error(f"Audio not found: {audio_path}")
                return None
            with open(path, "rb") as f:
                result = self._client_().audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                )
            logger.debug(f"Transcribed {path.name}: {len(result.text)} chars")
            return result.text
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return None
        finally:
            try:
                path.unlink(missing_ok=True)
                logger.debug(f"Deleted audio: {path.name}")
            except Exception:
                pass

    def _empty(self) -> dict:
        return {
            "has_task": False,
            "has_deadline": False,
            "deadline_text": None,
            "has_agreement": False,
            "has_question": False,
            "action_required": False,
            "urgency": "low",
            "has_file_request": False,
        }

    def _validate(self, raw: dict) -> dict:
        result = self._empty()
        for key in result:
            if key in raw:
                result[key] = raw[key]
        if result["urgency"] not in ("low", "medium", "high"):
            result["urgency"] = "medium"
        return result
