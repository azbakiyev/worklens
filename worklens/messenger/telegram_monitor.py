"""
Telegram Monitor -- connects to Telegram via MTProto (Telethon).
Works regardless of which device the user is on (phone, tablet, PC).

PRIVACY:
  - Message text analyzed and immediately discarded -- never stored
  - Voice files deleted after Whisper transcription
  - Only structured JSON intents written to SQLite
  - Session stored at ~/.worklens/telegram.session

SETUP: python main.py --setup-telegram
"""
import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

SESSION_PATH = Path.home() / ".worklens" / "telegram.session"
VOICE_CACHE  = Path.home() / ".worklens" / "voice_cache"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff"}


class TelegramMonitor:

    def __init__(self, db_manager, api_id, api_hash, openai_api_key, phone=""):
        self.db            = db_manager
        self._api_id       = api_id
        self._api_hash     = api_hash
        self._openai_key   = openai_api_key
        self._phone        = phone
        self._approved_ids: Set[int] = set()
        self._running      = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        VOICE_CACHE.mkdir(parents=True, exist_ok=True)

    def setup(self) -> bool:
        from telethon.sync import TelegramClient
        from worklens.messenger.chat_classifier import ChatClassifier, ChatInfo
        from worklens.messenger.setup_ui import open_chat_selector

        classifier = ChatClassifier(self.db)

        if classifier.has_approved_chats() and SESSION_PATH.exists():
            self._approved_ids = classifier.load_approved_ids()
            logger.info(f"Telegram already configured. Watching {len(self._approved_ids)} chats.")
            return True

        print("\n[WorkLens] Telegram Setup")
        print("=" * 50)
        print("  Session is stored locally -- never transmitted.\n")

        if not self._phone:
            self._phone = input("  Phone (+7...): ").strip()

        try:
            with TelegramClient(str(SESSION_PATH), self._api_id, self._api_hash) as client:
                client.start(phone=self._phone)
                me = client.get_me()
                name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                print(f"  Connected as: {name}\n")
                print("  Scanning chats (names only, no message content)...")

                chats = []
                for dialog in client.iter_dialogs(limit=150):
                    entity = dialog.entity
                    chat_type = "direct"
                    member_count = 0
                    if dialog.is_group:
                        chat_type    = "group"
                        member_count = getattr(entity, "participants_count", 0) or 0
                    elif dialog.is_channel:
                        chat_type    = "channel"
                        member_count = getattr(entity, "participants_count", 0) or 0
                    elif dialog.name == "Saved Messages":
                        chat_type = "saved"
                    chats.append(ChatInfo(
                        chat_id=dialog.id,
                        title=dialog.name or "Untitled",
                        chat_type=chat_type,
                        member_count=member_count,
                    ))

                classifier.classify(chats)
                approved = open_chat_selector(chats, self.db, classifier)
                self._approved_ids = {c.chat_id for c in approved}

        except Exception as e:
            logger.error(f"Telegram setup error: {e}")
            print(f"  Error: {e}")
            return False
        return True

    def start(self) -> None:
        if self._running:
            return
        if not SESSION_PATH.exists():
            logger.warning("No Telegram session. Run: python main.py --setup-telegram")
            return
        from worklens.messenger.chat_classifier import ChatClassifier
        self._approved_ids = ChatClassifier(self.db).load_approved_ids()
        if not self._approved_ids:
            logger.warning("No approved chats -- Telegram monitor skipped.")
            return
        self._running = True
        self._loop    = asyncio.new_event_loop()
        self._thread  = threading.Thread(target=self._run_loop, daemon=True, name="WorkLens-Telegram")
        self._thread.start()
        logger.info(f"Telegram monitor started | {len(self._approved_ids)} chats")

    def stop(self) -> None:
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            logger.error(f"Telegram loop error: {e}")

    async def _async_main(self) -> None:
        from telethon import TelegramClient, events
        async with TelegramClient(str(SESSION_PATH), self._api_id, self._api_hash) as client:
            @client.on(events.NewMessage(incoming=True))
            async def handler(event):
                try: await self._handle_event(event)
                except Exception as e: logger.error(f"Handler error: {e}")
            logger.info("Telethon connected -- listening...")
            await client.run_until_disconnected()

    async def _handle_event(self, event) -> None:
        if event.chat_id not in self._approved_ids:
            return
        msg = event.message
        if not msg: return
        if msg.voice or msg.audio:      await self._handle_voice(msg)
        elif msg.document or msg.photo: await self._handle_file(msg)
        elif msg.text:                  await self._handle_text(msg)

    async def _handle_text(self, msg) -> None:
        text = msg.text or ""
        if len(text.strip()) < 3: return
        intent = await asyncio.get_event_loop().run_in_executor(None, self._extract_intent, text)
        self._save_intent("telegram", msg.chat_id, intent)
        if intent.get("action_required") or intent.get("urgency") == "high":
            logger.info(f"[TG] Action required | chat={msg.chat_id} urgency={intent['urgency']}")

    async def _handle_voice(self, msg) -> None:
        path = VOICE_CACHE / f"voice_{msg.id}.ogg"
        try:
            await msg.download_media(str(path))
            intent = await asyncio.get_event_loop().run_in_executor(None, self._process_voice, str(path))
            self._save_intent("telegram_voice", msg.chat_id, intent)
            if intent.get("action_required"):
                logger.info(f"[TG] Voice task | chat={msg.chat_id}")
        except Exception as e:
            logger.error(f"Voice handler error: {e}")
            path.unlink(missing_ok=True)

    async def _handle_file(self, msg) -> None:
        doc = msg.document
        if not doc:
            self._save_file("telegram", "image", "photo"); return
        filename = ""
        for attr in (doc.attributes or []):
            if hasattr(attr, "file_name"): filename = attr.file_name or ""; break
        ext = Path(filename).suffix.lower()
        ftype = ("pdf" if ext == ".pdf" else
                 "spreadsheet" if ext in {".xls",".xlsx",".csv"} else
                 "document" if ext in {".doc",".docx"} else
                 "image" if ext in IMAGE_EXTENSIONS else "other")
        category = self._guess_category(filename)
        logger.info(f"[TG] File: {filename or 'unnamed'} [{ftype}] cat={category}")
        self._save_file("telegram", ftype, category)

    def _extract_intent(self, text):
        from worklens.messenger.intent_extractor import IntentExtractor
        return IntentExtractor(self._openai_key).extract_intent(text)

    def _process_voice(self, audio_path):
        from worklens.messenger.intent_extractor import IntentExtractor
        ex = IntentExtractor(self._openai_key)
        t  = ex.transcribe_voice(audio_path)
        return ex.extract_intent(t) if t else ex._empty()

    def _save_intent(self, source, chat_id, intent):
        from sqlalchemy import text
        itype = ("task" if intent.get("has_task") else
                 "agreement" if intent.get("has_agreement") else
                 "question" if intent.get("has_question") else
                 "file_request" if intent.get("has_file_request") else "info")
        try:
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO messenger_intents
                        (timestamp,source,chat_category,sender_role,intent_type,
                         has_deadline,deadline_dt,urgency,action_required,resolved)
                    VALUES (:ts,:src,:cat,'colleague',:itype,:hdl,NULL,:urgency,:action,0)
                """), {"ts": datetime.utcnow().isoformat(), "src": source,
                     "cat": f"tg_{chat_id}", "itype": itype,
                     "hdl": int(intent.get("has_deadline", False)),
                     "urgency": intent.get("urgency", "medium"),
                     "action": int(intent.get("action_required", False))})
        except Exception as e: logger.error(f"save_intent: {e}")

    def _save_file(self, source, ftype, category):
        from sqlalchemy import text
        try:
            with self.db.get_session() as session:
                session.execute(text("""
                    INSERT INTO received_files (timestamp,source,file_type,document_category,local_path,processed)
                    VALUES (:ts,:src,:ft,:cat,'',0)
                """), {"ts": datetime.utcnow().isoformat(),
                     "src": source, "ft": ftype, "cat": category})
        except Exception as e: logger.error(f"save_file: {e}")

    def _guess_category(self, filename):
        f = (filename or "").lower()
        if any(w in f for w in ["invoice","schet","naklad"]): return "invoice"
        if any(w in f for w in ["contract","dogovor"]):         return "contract"
        if any(w in f for w in ["proposal","kp","predloz"]):  return "proposal"
        if any(w in f for w in ["report","otchet","akt"]):    return "report"
        return "document"
