"""
WorkLens Dashboard -- unified web interface on http://localhost:7771

Routes:
  GET  /               -- single-page app (HTML)
  GET  /api/stats      -- overview stats
  GET  /api/patterns   -- detected patterns
  GET  /api/intents    -- messenger intents
  GET  /api/status     -- system status
  POST /api/intents/<id>/resolve
  POST /api/setup/send_code
  POST /api/setup/verify
  GET  /api/setup/chats
  POST /api/setup/save_chats
  GET  /setup/chats    -- standalone chat selector (reused from setup_ui)
"""
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request, render_template_string
from sqlalchemy import text

logger = logging.getLogger(__name__)
SESSION_PATH = Path.home() / ".worklens" / "telegram.session"

# Global state for web-based Telegram auth
_setup: Dict[str, Any] = {"client": None, "phone": None, "phone_hash": None}

# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WorkLens</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--g:#4caf50;--gl:#e8f5e9;--b:#2196f3;--bg:#f5f6fa;--card:#fff;
      --text:#1a1a1a;--muted:#888;--br:#e8eaed}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:var(--bg);color:var(--text);height:100vh;display:flex;overflow:hidden}

/* sidebar */
.sb{width:210px;background:var(--card);border-right:1px solid var(--br);
    display:flex;flex-direction:column;padding:20px 0;flex-shrink:0;height:100vh}
.logo{padding:0 18px 20px;font-size:17px;font-weight:700;color:var(--g);
      border-bottom:1px solid var(--br);margin-bottom:12px}
.logo small{font-size:11px;font-weight:400;color:var(--muted);display:block;margin-top:2px}
.ni{display:flex;align-items:center;gap:9px;padding:9px 18px;cursor:pointer;
    font-size:13px;font-weight:500;color:var(--muted);border-radius:0 8px 8px 0;
    margin-right:10px;transition:all .12s}
.ni:hover{background:var(--bg);color:var(--text)}
.ni.active{background:var(--gl);color:var(--g)}
.sb-foot{margin-top:auto;padding:14px 18px;font-size:12px;color:var(--muted)}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;
      padding:3px 9px;border-radius:999px;font-weight:500;margin-bottom:5px}
.pill.on{background:var(--gl);color:#2e7d32}
.pill.off{background:#f5f5f5;color:var(--muted);border:1px solid var(--br)}
.dot{width:6px;height:6px;border-radius:50%}
.dg{background:var(--g)}.dr{background:#ef5350}.do{background:#ff9800}

/* main */
.main{flex:1;overflow-y:auto;padding:28px 32px;height:100vh}
.sec{display:none}.sec.active{display:block}
.pt{font-size:21px;font-weight:700;margin-bottom:3px}
.ps{font-size:13px;color:var(--muted);margin-bottom:22px}

/* card */
.card{background:var(--card);border-radius:14px;padding:18px 22px;
      box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:14px}
.ct{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;
    letter-spacing:.06em;margin-bottom:12px}

/* stats */
.sr{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}
.sc{background:var(--card);border-radius:14px;padding:16px 18px;
    box-shadow:0 1px 4px rgba(0,0,0,.06)}
.sv{font-size:26px;font-weight:700}
.sl{font-size:12px;color:var(--muted);margin-top:3px}

/* app bar */
.ab{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.abf{flex:1;height:7px;background:var(--bg);border-radius:99px;overflow:hidden}
.abi{height:100%;background:var(--g);border-radius:99px;transition:width .3s}
.abp{font-size:12px;color:var(--muted);width:34px;text-align:right}
.abn{font-size:13px;font-weight:500;width:130px;white-space:nowrap;
     overflow:hidden;text-overflow:ellipsis}

/* pattern */
.pr{border-bottom:1px solid var(--br);padding:12px 0}
.pr:last-child{border-bottom:none}
.pseq{font-size:14px;font-weight:600;margin-bottom:3px}
.pm{font-size:12px;color:var(--muted)}
.sbar{height:5px;background:var(--bg);border-radius:99px;margin-top:7px;overflow:hidden}
.sfill{height:100%;border-radius:99px}

/* intent */
.ii{display:flex;align-items:flex-start;gap:12px;padding:12px 0;
    border-bottom:1px solid var(--br)}
.ii:last-child{border-bottom:none}
.iico{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;
      justify-content:center;font-size:17px;flex-shrink:0}
.iico.task{background:#fff3e0}.iico.question{background:#e3f2fd}
.iico.agreement{background:var(--gl)}.iico.file_request{background:#f3e5f5}
.ibody{flex:1}
.itype{font-size:13px;font-weight:600}
.imeta{font-size:12px;color:var(--muted);margin-top:2px}
.badge{display:inline-block;padding:2px 7px;border-radius:999px;
       font-size:11px;font-weight:600;margin-left:5px}
.badge.high{background:#ffebee;color:#c62828}
.badge.medium{background:#fff3e0;color:#e65100}
.badge.low{background:var(--gl);color:#2e7d32}

/* buttons */
.btn{padding:9px 18px;border-radius:9px;font-size:13px;font-weight:600;
     cursor:pointer;border:none;transition:all .12s}
.btn-p{background:var(--g);color:#fff}.btn-p:hover{background:#43a047}
.btn-o{background:#fff;color:var(--text);border:1.5px solid var(--br)}
.btn-o:hover{border-color:var(--g);color:var(--g)}
.btn-sm{padding:5px 12px;font-size:12px}

/* onboarding */
.ob{background:linear-gradient(135deg,#e8f5e9 0%,#e3f2fd 100%);
    border-radius:16px;padding:24px 28px;margin-bottom:16px;
    display:flex;align-items:center;justify-content:space-between}
.ob h2{font-size:17px;font-weight:700;margin-bottom:5px}
.ob p{font-size:13px;color:#555;max-width:380px;line-height:1.5}

/* settings */
.srow{display:flex;align-items:center;justify-content:space-between;
      padding:13px 0;border-bottom:1px solid var(--br)}
.srow:last-child{border-bottom:none}
.slab{font-size:14px;font-weight:500}
.sdesc{font-size:12px;color:var(--muted);margin-top:2px}

/* modal */
.mbg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);
     z-index:100;align-items:center;justify-content:center}
.mbg.open{display:flex}
.modal{background:#fff;border-radius:18px;padding:28px 30px;width:460px;
       box-shadow:0 20px 60px rgba(0,0,0,.15)}
.modal h3{font-size:17px;font-weight:700;margin-bottom:7px}
.modal p{font-size:13px;color:var(--muted);margin-bottom:18px;line-height:1.5}
.inp{width:100%;border:1.5px solid var(--br);border-radius:9px;
     padding:11px 13px;font-size:14px;outline:none;transition:border .12s}
.inp:focus{border-color:var(--g)}
.ilabel{font-size:12px;font-weight:500;margin-bottom:5px;display:block}
.ig{margin-bottom:13px}
.ma{display:flex;gap:9px;margin-top:18px}
.emsg{color:#ef5350;font-size:12px;margin-top:8px;min-height:16px}

/* chat card in modal */
.cc{display:flex;align-items:center;gap:11px;padding:9px;border-radius:10px;
    cursor:pointer;border:2px solid var(--br);background:#fff;
    margin-bottom:6px;transition:all .12s}
.cc.sel{border-color:var(--g);background:#f9fff9}
.cav{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
     justify-content:center;color:#fff;font-weight:700;font-size:13px;flex-shrink:0}
.cchk{width:19px;height:19px;border-radius:50%;border:2px solid #d1d5db;
      display:flex;align-items:center;justify-content:center;flex-shrink:0}
.cc.sel .cchk{background:var(--g);border-color:var(--g)}
</style>
</head>
<body>

<nav class="sb">
  <div class="logo">WorkLens <small>Automation Discovery</small></div>
  <div class="ni active" id="ni-overview"  onclick="nav('overview')"> <span>📊</span> Обзор</div>
  <div class="ni"        id="ni-patterns"  onclick="nav('patterns')"> <span>🔍</span> Паттерны</div>
  <div class="ni"        id="ni-tasks"     onclick="nav('tasks')">    <span>💬</span> Задачи</div>
  <div class="ni"        id="ni-settings"  onclick="nav('settings')"> <span>⚙️</span> Настройки</div>
  <div class="sb-foot" id="sbfoot">...</div>
</nav>

<main class="main">

<!-- OVERVIEW -->
<section class="sec active" id="sec-overview">
  <div class="pt">Обзор</div>
  <div class="ps" id="ov-date">Сегодня</div>
  <div class="ob" id="ob-card" style="display:none">
    <div>
      <h2>Добро пожаловать в WorkLens!</h2>
      <p>Подключите Telegram и WorkLens начнёт находить рутину и предлагать автоматизации через extella.</p>
    </div>
    <button class="btn btn-p" onclick="nav('settings');showSetup()">Начать →</button>
  </div>
  <div class="sr">
    <div class="sc"><div class="sv" id="st-ev">—</div><div class="sl">Событий сегодня</div></div>
    <div class="sc"><div class="sv" id="st-pt">—</div><div class="sl">Паттернов найдено</div></div>
    <div class="sc"><div class="sv" id="st-tk">—</div><div class="sl">Задач из Telegram</div></div>
    <div class="sc"><div class="sv" id="st-hr">—</div><div class="sl">ч рутины / нед</div></div>
  </div>
  <div class="card"><div class="ct">Активность</div><div id="ov-bars">...</div></div>
  <div class="card"><div class="ct">Топ паттерны</div><div id="ov-pats">...</div></div>
  <div class="card"><div class="ct">Последние задачи</div><div id="ov-tasks">...</div></div>
</section>

<!-- PATTERNS -->
<section class="sec" id="sec-patterns">
  <div class="pt">Паттерны</div>
  <div class="ps">Повторяющиеся процессы · потенциал автоматизации</div>
  <div class="card" id="pat-list">...</div>
</section>

<!-- TASKS -->
<section class="sec" id="sec-tasks">
  <div class="pt">Задачи из Telegram</div>
  <div class="ps">Обнаруженные задачи, договорённости и вопросы</div>
  <div class="card" id="task-list">...</div>
</section>

<!-- SETTINGS -->
<section class="sec" id="sec-settings">
  <div class="pt">Настройки</div>
  <div class="ps">Статус системы и управление подключениями</div>
  <div class="card"><div class="ct">Система</div><div id="set-sys">...</div></div>
  <div class="card"><div class="ct">Telegram</div><div id="set-tg">...</div></div>
  <div class="card">
    <div class="ct">Приватность</div>
    <div class="srow">
      <div><div class="slab">Тексты сообщений</div><div class="sdesc">Анализируются и сразу удаляются — не сохраняются</div></div>
      <span class="pill on"><span class="dot dg"></span>Защищено</span>
    </div>
    <div class="srow">
      <div><div class="slab">База данных</div><div class="sdesc">Только на вашем компьютере (~/.worklens/data.db)</div></div>
      <span class="pill on"><span class="dot dg"></span>Local only</span>
    </div>
  </div>
</section>

</main>

<!-- Setup Modal -->
<div class="mbg" id="modal">
  <div class="modal">
    <!-- step: phone -->
    <div id="st-phone">
      <h3>Подключить Telegram</h3>
      <p>Введите номер телефона. Telegram пришлёт код подтверждения в приложение.</p>
      <div class="ig"><label class="ilabel">Номер телефона</label>
        <input class="inp" id="inp-phone" type="tel" placeholder="+7..."></div>
      <div class="ma">
        <button class="btn btn-p" onclick="doSendCode()">Получить код</button>
        <button class="btn btn-o" onclick="closeModal()">Отмена</button>
      </div>
    </div>
    <!-- step: code -->
    <div id="st-code" style="display:none">
      <h3>Введите код</h3>
      <p>Telegram прислал код в ваше приложение.</p>
      <div class="ig"><label class="ilabel">Код из Telegram</label>
        <input class="inp" id="inp-code" type="text" placeholder="12345"></div>
      <div class="ma">
        <button class="btn btn-p" onclick="doVerify()">Подтвердить</button>
        <button class="btn btn-o" onclick="closeModal()">Отмена</button>
      </div>
    </div>
    <!-- step: chats -->
    <div id="st-chats" style="display:none">
      <h3>Выбери рабочие чаты</h3>
      <p>WorkLens будет анализировать только выбранные чаты. Тексты не сохраняются.</p>
      <div id="chats-wrap" style="max-height:300px;overflow-y:auto;margin-bottom:14px"></div>
      <div class="ma">
        <button class="btn btn-p" onclick="doSaveChats()">Сохранить и продолжить</button>
      </div>
    </div>
    <!-- step: done -->
    <div id="st-done" style="display:none;text-align:center;padding:16px 0">
      <div style="font-size:44px;margin-bottom:10px">✅</div>
      <h3>WorkLens настроен!</h3>
      <p style="margin-top:6px">Мониторинг Telegram активирован.</p>
      <button class="btn btn-p" style="margin-top:16px" onclick="closeModal();loadAll()">Готово</button>
    </div>
    <div class="emsg" id="emsg"></div>
  </div>
</div>

<script>
const COLORS = ['#4caf50','#2196f3','#ff9800','#9c27b0','#e91e63','#00bcd4','#607d8b'];
let _chats = [], _sel = new Set();

function nav(p) {
  document.querySelectorAll('.ni').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.sec').forEach(el=>el.classList.remove('active'));
  document.getElementById('ni-'+p).classList.add('active');
  document.getElementById('sec-'+p).classList.add('active');
  if(p==='overview') loadOverview();
  if(p==='patterns') loadPatterns();
  if(p==='tasks')    loadTasks();
  if(p==='settings') loadSettings();
}

async function loadAll() { loadOverview(); }

async function loadOverview() {
  const [stats, pats, tasks] = await Promise.all([
    get('/api/stats'), get('/api/patterns?limit=3'), get('/api/intents?limit=5')
  ]);
  const d = new Date();
  document.getElementById('ov-date').textContent =
    d.toLocaleDateString('ru-RU',{weekday:'long',day:'numeric',month:'long',year:'numeric'});

  document.getElementById('st-ev').textContent = (stats.events_today||0).toLocaleString();
  document.getElementById('st-pt').textContent = stats.patterns_total||0;
  document.getElementById('st-tk').textContent = stats.tasks_unresolved||0;
  document.getElementById('st-hr').textContent = stats.routine_hours_week||'0';

  document.getElementById('ob-card').style.display = stats.telegram_connected ? 'none':'flex';

  document.getElementById('ov-bars').innerHTML = (stats.top_apps||[]).length
    ? stats.top_apps.map(a=>`<div class="ab">
        <span class="abn">${esc(a.name)}</span>
        <div class="abf"><div class="abi" style="width:${a.pct}%"></div></div>
        <span class="abp">${a.pct}%</span></div>`).join('')
    : muted('Нет данных за сегодня');

  document.getElementById('ov-pats').innerHTML = pats.length
    ? pats.map(renderPat).join('') : muted('Паттерны накапливаются — продолжайте работать 😊');
  document.getElementById('ov-tasks').innerHTML = tasks.length
    ? tasks.map(renderIntent).join('') : muted('Задач из Telegram пока нет');

  document.getElementById('sbfoot').innerHTML = `
    <div><span class="pill ${stats.capture_running?'on':'off'}">
      <span class="dot ${stats.capture_running?'dg':'dr'}"></span>Capture</span></div>
    <div><span class="pill ${stats.telegram_connected?'on':'off'}">
      <span class="dot ${stats.telegram_connected?'dg':'dr'}"></span>Telegram</span></div>`;
}

async function loadPatterns() {
  const data = await get('/api/patterns');
  document.getElementById('pat-list').innerHTML = data.length
    ? data.map(p=>renderPat(p,true)).join('')
    : muted('Паттерны появятся через 2-3 дня работы. WorkLens уже наблюдает!');
}

async function loadTasks() {
  const data = await get('/api/intents');
  document.getElementById('task-list').innerHTML = data.length
    ? data.map(t=>renderIntent(t,true)).join('')
    : muted('Задач из Telegram пока нет');
}

async function loadSettings() {
  const s = await get('/api/status');
  document.getElementById('set-sys').innerHTML = `
    <div class="srow">
      <div><div class="slab">Activity Capture</div>
           <div class="sdesc">${(s.events_total||0).toLocaleString()} событий накоплено</div></div>
      <span class="pill ${s.capture_running?'on':'off'}">
        <span class="dot ${s.capture_running?'dg':'dr'}"></span>
        ${s.capture_running?'Работает':'Остановлен'}</span></div>
    <div class="srow">
      <div><div class="slab">OpenAI API</div><div class="sdesc">Анализ интентов и паттернов</div></div>
      <span class="pill ${s.openai_ok?'on':'off'}">
        <span class="dot ${s.openai_ok?'dg':'dr'}"></span>
        ${s.openai_ok?'Настроен':'Не настроен'}</span></div>`;

  document.getElementById('set-tg').innerHTML = s.telegram_user
    ? `<div class="srow">
         <div><div class="slab">Подключён: ${esc(s.telegram_user)}</div>
              <div class="sdesc">${s.chats_count} чатов мониторируется</div></div>
         <button class="btn btn-o btn-sm" onclick="openChatSelect()">Сменить чаты</button>
       </div>`
    : `<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0">
         <span style="font-size:13px;color:var(--muted)">Telegram не подключён</span>
         <button class="btn btn-p btn-sm" onclick="showSetup()">Подключить</button>
       </div>`;
}

// ── renderers ─────────────────────────────────────────────────────────────────
function renderPat(p, full=false) {
  const pct = Math.round((p.score||0)*100);
  const col = COLORS[Math.min(Math.floor(pct/20), COLORS.length-1)];
  return `<div class="pr">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div class="pseq">${esc(p.sequence)}</div>
        <div class="pm">${p.frequency}x &nbsp;·&nbsp; ~${p.time_min} мин/нед &nbsp;·&nbsp; ${esc(p.apps)}</div>
      </div>
      <div style="text-align:right;margin-left:12px;flex-shrink:0">
        <div style="font-size:20px;font-weight:700;color:${col}">${pct}%</div>
        <div style="font-size:11px;color:var(--muted)">потенциал</div>
      </div>
    </div>
    <div class="sbar"><div class="sfill" style="width:${pct}%;background:${col}"></div></div>
  </div>`;
}

function renderIntent(t, full=false) {
  const icons={task:'📋',question:'❓',agreement:'🤝',file_request:'📎',info:'ℹ️'};
  const labels={task:'Задача',question:'Вопрос',agreement:'Договорённость',file_request:'Файл',info:'Инфо'};
  const ulabels={high:'Срочно',medium:'Обычный',low:'Низкий'};
  const ts = new Date(t.timestamp).toLocaleString('ru-RU',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
  return `<div class="ii">
    <div class="iico ${t.type||'info'}">${icons[t.type]||'ℹ️'}</div>
    <div class="ibody">
      <div class="itype">${labels[t.type]||t.type}
        <span class="badge ${t.urgency||'medium'}">${ulabels[t.urgency]||t.urgency}</span>
        ${t.has_deadline?'<span class="badge medium">Дедлайн</span>':''}
      </div>
      <div class="imeta">${esc(t.source||'')} · ${ts}</div>
    </div>
    ${full&&!t.resolved?`<button class="btn btn-o btn-sm" onclick="resolve(${t.id})">✓</button>`:''}
  </div>`;
}

// ── setup modal ───────────────────────────────────────────────────────────────
function showSetup() {
  ['phone','code','chats','done'].forEach(s=>hide('st-'+s));
  show('st-phone'); setErr('');
  document.getElementById('modal').classList.add('open');
}
function openChatSelect() { window.open('/setup/chats','_blank','width=720,height=700'); }
function closeModal() { document.getElementById('modal').classList.remove('open'); }

async function doSendCode() {
  const phone = document.getElementById('inp-phone').value.trim();
  if(!phone){setErr('Введите номер');return}
  setErr('Отправляем...');
  const r = await post('/api/setup/send_code',{phone});
  if(r.ok){ setErr(''); hide('st-phone'); show('st-code'); }
  else setErr(r.error||'Ошибка');
}

async function doVerify() {
  const code = document.getElementById('inp-code').value.trim();
  if(!code){setErr('Введите код');return}
  setErr('Проверяем...');
  const r = await post('/api/setup/verify',{code});
  if(r.ok){
    setErr(''); hide('st-code'); show('st-chats');
    _chats = r.chats||[];
    _sel = new Set(_chats.filter(c=>c.suggested).map(c=>c.id));
    renderChats();
  } else setErr(r.error||'Неверный код');
}

function renderChats() {
  const work=_chats.filter(c=>c.suggested), other=_chats.filter(c=>!c.suggested);
  let h='';
  if(work.length) h+=`<div style="font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;padding:8px 0 4px">Рабочие (${work.length})</div>`+work.map(chatCard).join('');
  if(other.length) h+=`<div style="font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;padding:8px 0 4px">Остальные (${other.length})</div>`+other.map(chatCard).join('');
  document.getElementById('chats-wrap').innerHTML=h;
}
function chatCard(c){
  const s=_sel.has(c.id),col=COLORS[c.title.split('').reduce((a,x)=>a+x.charCodeAt(0),0)%COLORS.length];
  return `<div class="cc${s?' sel':''}" onclick="toggleC(${c.id},this)">
    <div class="cav" style="background:${col}">${c.title[0]||'?'}</div>
    <div style="flex:1;font-size:13px;font-weight:500">${esc(c.title)}</div>
    <div style="font-size:11px;color:var(--muted)">${c.members||c.type}</div>
    <div class="cchk">${s?chk():''}</div>
  </div>`;
}
function toggleC(id,el){
  _sel.has(id)?_sel.delete(id):_sel.add(id);
  const s=_sel.has(id);
  el.classList.toggle('sel',s);
  el.querySelector('.cchk').innerHTML=s?chk():'';
}
function chk(){return '<svg width="10" height="8" fill="none"><path d="M1 4l2.5 2.5L9 1" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>';}

async function doSaveChats() {
  const r = await post('/api/setup/save_chats',{selected:[..._sel]});
  if(r.ok){hide('st-chats');show('st-done');}
  else setErr(r.error||'Ошибка сохранения');
}

async function resolve(id){
  await post('/api/intents/'+id+'/resolve',{});
  loadTasks();
}

// ── utils ─────────────────────────────────────────────────────────────────────
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function muted(s){return `<span style="color:var(--muted);font-size:13px">${s}</span>`;}
function show(id){document.getElementById(id).style.display='block';}
function hide(id){document.getElementById(id).style.display='none';}
function setErr(m){document.getElementById('emsg').textContent=m;}
async function get(url){try{return await fetch(url).then(r=>r.json());}catch{return {};}}
async function post(url,d){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)}).then(r=>r.json()).catch(e=>({ok:false,error:String(e)}));}

loadOverview();
setInterval(loadOverview, 30000);
</script>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Flask app factory
# ─────────────────────────────────────────────────────────────────────────────
def create_app(db_manager, config_manager, capture=None, tg_monitor=None):
    app = Flask(__name__)
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    # ── helpers ───────────────────────────────────────────────────────────────
    def db():
        return db_manager

    def cfg():
        return config_manager

    def _run_tg_sync(coro):
        """Run a Telethon async coroutine synchronously in a fresh event loop."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # ── HTML ──────────────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template_string(HTML)

    # Standalone chat selector (reuses setup_ui logic)
    @app.route("/setup/chats")
    def setup_chats_page():
        from worklens.messenger.setup_ui import _build_html
        from worklens.messenger.chat_classifier import ChatClassifier, ChatInfo
        from telethon.sync import TelegramClient as SyncClient

        classifier = ChatClassifier(db_manager)
        chats_info = []

        try:
            with SyncClient(
                str(SESSION_PATH),
                config_manager.get("telegram_api_id"),
                config_manager.get("telegram_api_hash"),
            ) as client:
                client.start()
                for dialog in client.iter_dialogs(limit=150):
                    if dialog.is_channel:
                        continue
                    entity = dialog.entity
                    ctype = "direct"
                    mc = 0
                    if dialog.is_group:
                        ctype = "group"
                        mc = getattr(entity, "participants_count", 0) or 0
                    elif dialog.name == "Saved Messages":
                        ctype = "saved"
                    chats_info.append(
                        ChatInfo(dialog.id, dialog.name or "Untitled", ctype, mc)
                    )
            classifier.classify(chats_info)
        except Exception as e:
            logger.error(f"Chat selector page error: {e}")

        return _build_html(chats_info)

    # ── API: stats ─────────────────────────────────────────────────────────────
    @app.route("/api/stats")
    def api_stats():
        today = datetime.utcnow().date().isoformat()
        with db().get_session() as s:
            ev_today = s.execute(
                text("SELECT COUNT(*) FROM activity_events WHERE timestamp >= :d"),
                {"d": today},
            ).scalar() or 0

            top = s.execute(
                text(
                    "SELECT app_name, COUNT(*) c FROM activity_events "
                    "WHERE timestamp >= :d GROUP BY app_name ORDER BY c DESC LIMIT 6"
                ),
                {"d": today},
            ).fetchall()

            total_top = sum(r[1] for r in top) or 1

            pats = s.execute(text("SELECT COUNT(*) FROM detected_patterns")).scalar() or 0
            tasks = s.execute(
                text(
                    "SELECT COUNT(*) FROM messenger_intents "
                    "WHERE action_required=1 AND resolved=0"
                )
            ).scalar() or 0

        approved_chats = 0
        tg_user = cfg().get("telegram_user", "")
        try:
            from worklens.messenger.chat_classifier import ChatClassifier
            approved_chats = len(ChatClassifier(db_manager).load_approved_ids())
        except Exception:
            pass

        return jsonify(
            {
                "events_today": ev_today,
                "patterns_total": pats,
                "tasks_unresolved": tasks,
                "routine_hours_week": round(ev_today * 5 / 3600, 1),
                "capture_running": bool(capture and capture.is_running),
                "telegram_connected": bool(
                    SESSION_PATH.exists() and approved_chats > 0
                ),
                "top_apps": [
                    {"name": r[0], "pct": round(r[1] / total_top * 100)}
                    for r in top
                ],
            }
        )

    # ── API: patterns ─────────────────────────────────────────────────────────
    @app.route("/api/patterns")
    def api_patterns():
        limit = int(request.args.get("limit", 50))
        with db().get_session() as s:
            rows = s.execute(
                text(
                    "SELECT id, pattern_type, description, frequency, "
                    "time_consumed_minutes, automation_score "
                    "FROM detected_patterns ORDER BY automation_score DESC LIMIT :lim"
                ),
                {"lim": limit},
            ).fetchall()

        result = []
        for r in rows:
            desc = r[2] or ""
            # Extract apps from description if present
            apps = ""
            if "apps=" in desc:
                apps = desc.split("apps=")[-1].split("]")[0].strip("[ '\"")
            result.append(
                {
                    "id": r[0],
                    "type": r[1],
                    "sequence": desc.split(" apps=")[0] if "apps=" in desc else desc or r[1],
                    "frequency": r[3],
                    "time_min": round(r[4] or 0),
                    "score": round(r[5] or 0, 2),
                    "apps": apps,
                }
            )
        return jsonify(result)

    # ── API: intents ──────────────────────────────────────────────────────────
    @app.route("/api/intents")
    def api_intents():
        limit = int(request.args.get("limit", 50))
        with db().get_session() as s:
            rows = s.execute(
                text(
                    "SELECT id, timestamp, source, intent_type, "
                    "urgency, has_deadline, action_required, resolved "
                    "FROM messenger_intents ORDER BY timestamp DESC LIMIT :lim"
                ),
                {"lim": limit},
            ).fetchall()

        return jsonify(
            [
                {
                    "id": r[0],
                    "timestamp": str(r[1]),
                    "source": r[2],
                    "type": r[3],
                    "urgency": r[4],
                    "has_deadline": bool(r[5]),
                    "action_required": bool(r[6]),
                    "resolved": bool(r[7]),
                }
                for r in rows
            ]
        )

    @app.route("/api/intents/<int:intent_id>/resolve", methods=["POST"])
    def api_resolve_intent(intent_id: int):
        with db().get_session() as s:
            s.execute(
                text("UPDATE messenger_intents SET resolved=1 WHERE id=:id"),
                {"id": intent_id},
            )
        return jsonify({"ok": True})

    # ── API: status ───────────────────────────────────────────────────────────
    @app.route("/api/status")
    def api_status():
        with db().get_session() as s:
            total = s.execute(text("SELECT COUNT(*) FROM activity_events")).scalar() or 0
            chats_count = 0
            try:
                from worklens.messenger.chat_classifier import ChatClassifier
                chats_count = len(ChatClassifier(db_manager).load_approved_ids())
            except Exception:
                pass

        return jsonify(
            {
                "capture_running": bool(capture and capture.is_running),
                "events_total": total,
                "openai_ok": cfg().has("openai_api_key"),
                "telegram_user": cfg().get("telegram_user", ""),
                "chats_count": chats_count,
            }
        )

    # ── API: Telegram setup ────────────────────────────────────────────────────
    @app.route("/api/setup/send_code", methods=["POST"])
    def api_send_code():
        phone = (request.json or {}).get("phone", "").strip()
        if not phone:
            return jsonify({"ok": False, "error": "Введите номер телефона"})

        api_id = cfg().get("telegram_api_id")
        api_hash = cfg().get("telegram_api_hash")
        if not api_id or not api_hash:
            return jsonify({"ok": False, "error": "api_id / api_hash не настроены"})

        try:
            from telethon import TelegramClient as AsyncClient

            async def _send():
                client = AsyncClient(str(SESSION_PATH), api_id, api_hash)
                await client.connect()
                if await client.is_user_authorized():
                    _setup["client"] = client
                    _setup["phone"] = phone
                    return {"already_auth": True}
                result = await client.send_code_request(phone)
                _setup["client"] = client
                _setup["phone"] = phone
                _setup["phone_hash"] = result.phone_code_hash
                return {"ok": True}

            r = _run_tg_sync(_send())
            if r.get("already_auth"):
                return jsonify({"ok": True, "already_auth": True})
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/setup/verify", methods=["POST"])
    def api_verify():
        code = (request.json or {}).get("code", "").strip()
        client = _setup.get("client")
        phone = _setup.get("phone")
        phone_hash = _setup.get("phone_hash")

        if not client or not phone:
            return jsonify({"ok": False, "error": "Сначала отправьте код"})

        try:
            async def _verify():
                try:
                    await client.sign_in(
                        phone=phone, code=code, phone_code_hash=phone_hash
                    )
                except Exception as e:
                    raise e

                me = await client.get_me()
                name = f"{me.first_name or ''} {me.last_name or ''}".strip()

                # Scan chats
                from worklens.messenger.chat_classifier import ChatClassifier, ChatInfo

                chats = []
                async for dialog in client.iter_dialogs(limit=150):
                    if dialog.is_channel:
                        continue
                    entity = dialog.entity
                    ctype = "direct"
                    mc = 0
                    if dialog.is_group:
                        ctype = "group"
                        mc = getattr(entity, "participants_count", 0) or 0
                    elif dialog.name == "Saved Messages":
                        ctype = "saved"
                    chats.append(
                        ChatInfo(dialog.id, dialog.name or "Untitled", ctype, mc)
                    )

                clf = ChatClassifier(db_manager)
                clf.classify(chats)
                return name, chats

            name, chats = _run_tg_sync(_verify())
            cfg().set("telegram_user", name)

            return jsonify(
                {
                    "ok": True,
                    "user": name,
                    "chats": [
                        {
                            "id": c.chat_id,
                            "title": c.title,
                            "type": c.chat_type,
                            "members": c.member_count,
                            "suggested": c.is_suggested_work,
                        }
                        for c in chats
                    ],
                }
            )
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/setup/save_chats", methods=["POST"])
    def api_save_chats():
        selected_ids = set((request.json or {}).get("selected", []))
        client = _setup.get("client")

        if not client:
            return jsonify({"ok": False, "error": "Нет активной сессии"})

        try:
            from worklens.messenger.chat_classifier import ChatClassifier, ChatInfo

            async def _get_chats():
                chats = []
                async for dialog in client.iter_dialogs(limit=150):
                    if dialog.is_channel:
                        continue
                    entity = dialog.entity
                    ctype = "direct"
                    mc = 0
                    if dialog.is_group:
                        ctype = "group"
                        mc = getattr(entity, "participants_count", 0) or 0
                    elif dialog.name == "Saved Messages":
                        ctype = "saved"
                    chats.append(
                        ChatInfo(dialog.id, dialog.name or "Untitled", ctype, mc)
                    )
                return chats

            all_chats = _run_tg_sync(_get_chats())
            approved = [c for c in all_chats if c.chat_id in selected_ids]

            clf = ChatClassifier(db_manager)
            clf.save_approved(approved)

            # Restart tg_monitor if running
            if tg_monitor:
                try:
                    tg_monitor.stop()
                    tg_monitor._approved_ids = {c.chat_id for c in approved}
                    tg_monitor.start()
                except Exception as e:
                    logger.warning(f"Could not restart tg_monitor: {e}")

            return jsonify({"ok": True, "count": len(approved)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Start dashboard in background thread
# ─────────────────────────────────────────────────────────────────────────────
def start_dashboard(
    db_manager,
    config_manager,
    capture=None,
    tg_monitor=None,
    port: int = 7771,
):
    """Start WorkLens dashboard in a background daemon thread."""
    app = create_app(db_manager, config_manager, capture, tg_monitor)

    def _run():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    t = threading.Thread(target=_run, daemon=True, name="WorkLens-Dashboard")
    t.start()
    logger.info(f"Dashboard running at http://localhost:{port}")
    return app
