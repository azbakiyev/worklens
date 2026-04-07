"""
Setup UI -- web interface for selecting Telegram chats to monitor.
Opens automatically in browser on http://localhost:7771
Closes itself after user saves selection.
"""
import json
import logging
import threading
import webbrowser
from typing import List

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WorkLens -- Select Chats</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f2f5; min-height: 100vh; padding: 32px 16px; }
  .container { max-width: 680px; margin: 0 auto; }
  .header { background: #fff; border-radius: 16px; padding: 28px 32px;
            box-shadow: 0 2px 12px rgba(0,0,0,.08); margin-bottom: 16px; }
  .header h1 { font-size: 22px; font-weight: 700; color: #1a1a1a; }
  .header p  { margin-top: 8px; color: #666; font-size: 14px; line-height: 1.5; }
  .badge-work     { display:inline-block; background:#e8f5e9; color:#2e7d32;
                    font-size:11px; font-weight:600; padding:2px 8px;
                    border-radius:999px; margin-left:8px; }
  .badge-personal { display:inline-block; background:#f3f4f6; color:#6b7280;
                    font-size:11px; font-weight:600; padding:2px 8px;
                    border-radius:999px; margin-left:8px; }
  .section-title { font-size:12px; font-weight:600; color:#888;
                   text-transform:uppercase; letter-spacing:.06em;
                   margin: 20px 0 8px; padding: 0 4px; }
  .chat-card { background:#fff; border-radius:12px; padding:14px 18px;
               margin-bottom:8px; display:flex; align-items:center; gap:14px;
               box-shadow:0 1px 4px rgba(0,0,0,.06); cursor:pointer;
               transition: box-shadow .15s, border .15s;
               border: 2px solid transparent; }
  .chat-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.10); }
  .chat-card.selected { border-color: #4caf50; background:#f9fff9; }
  .chat-avatar { width:42px; height:42px; border-radius:50%;
                 display:flex; align-items:center; justify-content:center;
                 font-size:18px; font-weight:700; flex-shrink:0; color:#fff; }
  .chat-info { flex:1; min-width:0; }
  .chat-title { font-size:15px; font-weight:600; color:#1a1a1a;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .chat-meta  { font-size:12px; color:#999; margin-top:2px; }
  .check { width:22px; height:22px; border-radius:50%; border:2px solid #d1d5db;
           display:flex; align-items:center; justify-content:center;
           flex-shrink:0; transition: all .15s; }
  .chat-card.selected .check { background:#4caf50; border-color:#4caf50; }
  .check svg { display:none; }
  .chat-card.selected .check svg { display:block; }
  .footer { position:sticky; bottom:0; background:#fff; border-radius:16px;
            padding:20px 32px; box-shadow:0 -4px 24px rgba(0,0,0,.08);
            margin-top:20px; display:flex; align-items:center;
            justify-content:space-between; }
  .footer .count { font-size:14px; color:#666; }
  .footer .count span { font-weight:700; color:#1a1a1a; }
  .btn-save { background:#4caf50; color:#fff; border:none; padding:12px 32px;
              border-radius:10px; font-size:15px; font-weight:600; cursor:pointer;
              transition: background .15s; }
  .btn-save:hover { background:#43a047; }
  .btn-save:disabled { background:#a5d6a7; cursor:not-allowed; }
  .saved-msg { display:none; text-align:center; padding:40px;
               font-size:18px; color:#2e7d32; font-weight:600; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>WorkLens -- Выбери рабочие чаты</h1>
    <p>WorkLens будет анализировать только выбранные чаты.<br>
       Текст сообщений <strong>не сохраняется</strong> -- только структурные паттерны (задачи, файлы, договоренности).</p>
  </div>

  <div id="main">
    __CHAT_SECTIONS__
  </div>

  <div class="footer">
    <div class="count">Выбрано: <span id="cnt">0</span> чатов</div>
    <button class="btn-save" id="saveBtn" onclick="save()">Сохранить и продолжить</button>
  </div>
</div>

<script>
const allChats = __CHATS_JSON__;
const selected = new Set(allChats.filter(c => c.suggested).map(c => c.id));

function updateCount() {
  document.getElementById('cnt').textContent = selected.size;
}

function toggle(id) {
  const card = document.getElementById('card_' + id);
  if (selected.has(id)) { selected.delete(id); card.classList.remove('selected'); }
  else                   { selected.add(id);    card.classList.add('selected');    }
  updateCount();
}

function save() {
  const btn = document.getElementById('saveBtn');
  btn.disabled = true; btn.textContent = 'Сохраняю...';
  fetch('/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({selected: [...selected]})
  }).then(r => r.json()).then(d => {
    if (d.ok) {
      document.querySelector('.container').innerHTML =
        '<div class="saved-msg" style="display:block">✅ ' + d.count +
        ' чатов сохранено.<br><small>Можно закрыть эту вкладку.</small></div>';
      setTimeout(() => window.close(), 2000);
    }
  });
}

updateCount();
</script>
</body></html>"""


def _avatar_color(title: str) -> str:
    colors = ["#4caf50","#2196f3","#9c27b0","#ff9800","#e91e63","#00bcd4","#607d8b"]
    return colors[sum(ord(c) for c in title) % len(colors)]


def _build_html(chats) -> str:
    chats_json = json.dumps([
        {
            "id": c.chat_id,
            "title": c.title,
            "type": c.chat_type,
            "members": c.member_count,
            "suggested": c.is_suggested_work,
        }
        for c in chats
    ], ensure_ascii=False)

    work    = [c for c in chats if c.is_suggested_work]
    other   = [c for c in chats if not c.is_suggested_work]

    def card(c) -> str:
        sel   = "selected" if c.is_suggested_work else ""
        color = _avatar_color(c.title)
        emoji = {"group": "G", "channel": "C", "direct": "D", "saved": "S"}.get(c.chat_type, "?")
        members_txt = f"{c.member_count} участников" if c.member_count else c.chat_type
        return (
            f'<div class="chat-card {sel}" id="card_{c.chat_id}" onclick="toggle({c.chat_id})">  '
            f'<div class="chat-avatar" style="background:{color}">{emoji}</div>  '
            f'<div class="chat-info">    '
            f'<div class="chat-title">{c.title}</div>    '
            f'<div class="chat-meta">{members_txt}</div>  '
            f'</div>  '
            f'<div class="check">    '
            f'<svg width="12" height="10" viewBox="0 0 12 10" fill="none">      '
            f'<path d="M1 5l3.5 3.5L11 1" stroke="white" stroke-width="2" stroke-linecap="round"/>    '
            f'</svg>  </div></div>'
        )

    sections = ""
    if work:
        sections += '<div class="section-title">Рабочие чаты (' + str(len(work)) + ')</div>'
        sections += "\n".join(card(c) for c in work)
    if other:
        sections += '<div class="section-title">Остальные (' + str(len(other)) + ')</div>'
        sections += "\n".join(card(c) for c in other)

    return (HTML_TEMPLATE
            .replace("__CHAT_SECTIONS__", sections)
            .replace("__CHATS_JSON__", chats_json))


def open_chat_selector(chats, db_manager, classifier) -> List:
    """
    Start a local Flask server, open browser, wait for user to save.
    Returns list of approved ChatInfo objects.
    """
    from flask import Flask, request, jsonify
    import threading

    app = Flask(__name__)
    app.logger.disabled = True
    import logging as _log
    _log.getLogger('werkzeug').setLevel(_log.ERROR)

    result_holder = {"approved": None, "done": threading.Event()}
    chat_map = {c.chat_id: c for c in chats}

    @app.route('/')
    def index():
        return _build_html(chats)

    @app.route('/save', methods=['POST'])
    def save():
        data = request.get_json()
        selected_ids = set(data.get('selected', []))
        approved = [chat_map[cid] for cid in selected_ids if cid in chat_map]
        result_holder['approved'] = approved
        classifier.save_approved(approved)
        result_holder['done'].set()
        return jsonify({'ok': True, 'count': len(approved)})

    server = threading.Thread(
        target=lambda: app.run(host='127.0.0.1', port=7771, debug=False, use_reloader=False),
        daemon=True
    )
    server.start()

    import time; time.sleep(0.5)
    webbrowser.open('http://localhost:7771')
    print("\n[WorkLens] Chat selector opened in browser: http://localhost:7771")
    print("  Select work chats and click Save. Then return here.\n")

    result_holder['done'].wait()
    approved = result_holder['approved'] or []
    print(f"[WorkLens] Saved {len(approved)} chats. Continuing...\n")
    return approved
