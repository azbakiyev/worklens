# WorkLens 👁️

> AI-powered work activity analyzer and automation discovery tool

WorkLens — десктопный агент, который наблюдает за ежедневной работой сотрудника, анализирует паттерны активности и коммуникаций в мессенджерах, и предлагает конкретные автоматизации через extella.

## 🎯 Концепция

```
[Наблюдение] → [Анализ паттернов] → [Отчёт с ROI] → [Автоматизация через extella]
```

WorkLens решает главную боль автоматизационного консалтинга: вместо субъективных интервью — реальные данные о том, где и сколько времени тратится на рутину.

## 🏗️ Архитектура

```
worklens/
├── capture/          # Модуль захвата активности (приложения, окна, буфер)
├── messenger/        # Модуль анализа мессенджеров (Telegram, WhatsApp)
├── pattern/          # Движок обнаружения паттернов (PrefixSpan, DBSCAN)
├── storage/          # Локальная БД (SQLite + AES-256)
├── extella/          # Интеграция с extella AI Engine
├── ui/               # Системный трей + дашборд (PyQt6)
└── reports/          # Генератор PDF-отчётов для клиентов
```

## 📦 Модули

### 1. Capture Module ✅
Мониторинг активных приложений, категоризация (spreadsheet/browser/email/etc.), тип данных в буфере обмена. Работает на Windows / macOS / Linux. Никаких кейлоггеров — только структурные метаданные. Privacy zones — автоматическая пауза при открытии менеджеров паролей и банк-клиентов.

### 2. Storage / Database ✅
SQLAlchemy + SQLite. Таблицы: `activity_events`, `detected_patterns`, `automation_suggestions`, `messenger_intents`, `received_files`. Контекстный менеджер сессий с авто-rollback. Все данные — только на локальной машине.

### 3. Messenger Intelligence Module
Подключается к Telegram (Telethon MTProto API) и WhatsApp. Анализирует сообщения на наличие задач, договорённостей, файлов — **без хранения текста сообщений**.

### 4. Pattern Engine
Алгоритмы: PrefixSpan (частые последовательности приложений), DBSCAN (кластеризация сессий), Prophet (временные паттерны). Скоринг паттернов по частоте × время × потенциал автоматизации.

### 5. extella Integration
Мост между обнаружением паттернов и реализацией автоматизаций. Каждый паттерн с высоким score превращается в задание для extella агента.

### 6. Report Generator
Генерация PDF-отчёта для клиентов: топ возможностей автоматизации, расчёт ROI, дорожная карта внедрения.

## 🔒 Принципы приватности

- ✅ Все данные хранятся **только локально** (SQLite)
- ✅ Текст сообщений **не сохраняется** — только структурные интенты
- ✅ Сотрудник сам выбирает какие чаты анализировать
- ✅ Privacy zones — автоматическая пауза при открытии 1Password, Keychain, банк-клиентов
- ✅ Одна кнопка «Удалить все мои данные»

## 🛠️ Технологии

| Компонент | Технология |
|---|---|
| Desktop UI | PyQt6 + pystray |
| Мониторинг активности | osascript (Mac) / win32gui (Win) / xdotool (Linux) |
| Telegram | Telethon (MTProto API) |
| Pattern Mining | mlxtend (PrefixSpan) |
| Clustering | scikit-learn (DBSCAN) |
| Local LLM | Ollama + llama3.2 |
| Cloud LLM | Claude API / GPT-4o |
| OCR | Groq Vision (Llama 4 Scout) |
| База данных | SQLite + SQLAlchemy |
| Отчёты | ReportLab |
| Сборка | PyInstaller |

## 🚀 Установка и запуск (разработка)

```bash
git clone https://github.com/azbakiyev/worklens.git
cd worklens
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Что увидите:**
```
2026-04-06 10:30:00 [INFO] worklens: 🔵 WorkLens starting...
2026-04-06 10:30:00 [INFO] worklens: ✅ Database ready at ~/.worklens/data.db
2026-04-06 10:30:00 [INFO] worklens: ✅ Capture started — polling every 5 seconds
# Каждые 30 сек:
2026-04-06 10:30:30 [INFO] worklens: 📊 Total events: 6
2026-04-06 10:30:30 [INFO] worklens:    Google Chrome              4 events
2026-04-06 10:30:30 [INFO] worklens:    Terminal                   2 events
```

## 📁 Структура файлов

```
worklens/
├── main.py                          # Точка входа
├── requirements.txt
├── config.yaml                      # Конфигурация (без секретов)
├── worklens/
│   ├── capture/
│   │   ├── __init__.py
│   │   └── capture_module.py        # ✅ Готово: захват + категоризация
│   ├── messenger/
│   │   ├── telegram_monitor.py      # ⏳ Следующий этап
│   │   ├── whatsapp_monitor.py
│   │   └── intent_extractor.py
│   ├── pattern/
│   │   ├── pattern_engine.py        # ⏳ Запланирован
│   │   ├── sequence_miner.py
│   │   ├── time_analyzer.py
│   │   └── scorer.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py              # ✅ Готово: DatabaseManager
│   │   └── models.py                # ✅ Готово: 5 таблиц
│   ├── extella/
│   │   ├── extella_client.py        # ⏳ Запланирован
│   │   └── automation_builder.py
│   ├── ui/
│   │   ├── tray.py                  # ⏳ Запланирован
│   │   ├── dashboard.py
│   │   └── messenger_center.py
│   └── reports/
│       ├── report_generator.py      # ⏳ Запланирован
│       └── roi_calculator.py
└── tests/
    ├── test_capture.py
    ├── test_pattern.py
    └── test_messenger.py
```

## 📊 Tasks & Progress

| Модуль | Статус | Заметки |
|---|---|---|
| Storage / DB | ✅ Готово | SQLite + 5 таблиц (models.py + database.py) |
| Capture Module | ✅ Готово | macOS/Win/Linux, категоризация, privacy zones |
| main.py (точка входа) | ✅ Готово | Запуск + статистика каждые 30 сек |
| Pattern Engine | ⏳ Следующий | PrefixSpan + DBSCAN + Prophet |
| Telegram Monitor | ⏳ Следующий | Telethon MTProto |
| WhatsApp Monitor | ⏳ Запланирован | Web / Business API |
| extella Integration | ⏳ Запланирован | REST API клиент |
| UI / Tray | ⏳ Запланирован | PyQt6 + pystray |
| Report Generator | ⏳ Запланирован | PDF для клиентов |

## 📝 Правила разработки

1. **Никаких хардкодов** — все конфиги через `config.yaml` или `.env`
2. **Privacy First** — текст сообщений никогда не сохраняется
3. **Модульность** — каждый модуль тестируется независимо
4. **Точечные правки** — при фиксе бага меняем только сломанное место
5. **README актуален** — после каждого значимого изменения обновляем таблицу Tasks & Progress
6. **Типизация** — все функции с type hints
7. **Логирование** — `logging` вместо `print`

## 🔗 Связанные проекты

- [extella Platform](https://extella.ai) — AI Engine для реализации автоматизаций

---
*WorkLens — часть экосистемы автоматизации бизнеса на базе extella*
