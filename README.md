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

### 1. Capture Module
Мониторинг активных приложений, заголовков окон, типов данных в буфере обмена. Работает на Windows / macOS / Linux. Никаких кейлоггеров — только структурные метаданные.

### 2. Messenger Intelligence Module  
Подключается к Telegram (Telethon MTProto API) и WhatsApp (Web/Business API). Анализирует сообщения на наличие задач, договорённостей, файлов — **без хранения текста сообщений**.

### 3. Pattern Engine
Алгоритмы: PrefixSpan (частые последовательности приложений), DBSCAN (кластеризация сессий), Prophet (временные паттерны). Скоринг паттернов по частоте × время × потенциал автоматизации.

### 4. extella Integration
Мост между обнаружением паттернов и реализацией автоматизаций. Каждый паттерн с высоким score превращается в задание для extella агента.

### 5. Report Generator
Генерация PDF-отчёта для клиентов: топ возможностей автоматизации, расчёт ROI, дорожная карта внедрения.

## 🔒 Принципы приватности

- ✅ Все данные хранятся **только локально** (SQLite + AES-256)
- ✅ Текст сообщений **не сохраняется** — только структурные интенты
- ✅ Сотрудник сам выбирает какие чаты анализировать
- ✅ Privacy zones — исключение приложений и временных окон
- ✅ Одна кнопка «Удалить все мои данные»

## 🛠️ Технологии

| Компонент | Технология |
|---|---|
| Desktop UI | PyQt6 + pystray |
| Мониторинг активности | pygetwindow + win32gui (Win) / AppKit (Mac) |
| Telegram | Telethon (MTProto API) |
| Pattern Mining | mlxtend (PrefixSpan) |
| Clustering | scikit-learn (DBSCAN) |
| Local LLM | Ollama + llama3.2 |
| Cloud LLM | Claude API / GPT-4o |
| OCR | Groq Vision (Llama 4 Scout) |
| База данных | SQLite + SQLCipher (AES-256) |
| Отчёты | ReportLab |
| Сборка | PyInstaller |

## 🚀 Установка (разработка)

```bash
git clone https://github.com/azbakiyev/worklens.git
cd worklens
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 📁 Структура файлов

```
worklens/
├── main.py                      # Точка входа
├── requirements.txt
├── config.yaml                  # Конфигурация (без секретов)
├── .env.example                 # Пример env переменных
├── worklens/
│   ├── capture/
│   │   ├── capture_module.py    # Основной захват активности
│   │   └── platform_adapters/  # Win / Mac / Linux адаптеры
│   ├── messenger/
│   │   ├── telegram_monitor.py  # Telethon интеграция
│   │   ├── whatsapp_monitor.py  # WhatsApp Web / Business API
│   │   └── intent_extractor.py  # LLM-анализ интентов
│   ├── pattern/
│   │   ├── pattern_engine.py    # Основной движок
│   │   ├── sequence_miner.py    # PrefixSpan
│   │   ├── time_analyzer.py     # Временные паттерны
│   │   └── scorer.py            # Скоринг автоматизации
│   ├── storage/
│   │   ├── database.py          # SQLite + шифрование
│   │   └── models.py            # SQLAlchemy модели
│   ├── extella/
│   │   ├── extella_client.py    # REST API клиент
│   │   └── automation_builder.py
│   ├── ui/
│   │   ├── tray.py              # Системный трей
│   │   ├── dashboard.py         # Главный дашборд
│   │   └── messenger_center.py  # Центр мессенджеров
│   └── reports/
│       ├── report_generator.py  # PDF генератор
│       └── roi_calculator.py    # Расчёт ROI
└── tests/
    ├── test_capture.py
    ├── test_pattern.py
    └── test_messenger.py
```

## 📊 Tasks & Progress

| Модуль | Статус | Заметки |
|---|---|---|
| Capture Module | 🟡 В разработке | Базовый захват активности |
| Storage / DB | 🟡 В разработке | SQLite схема |
| Pattern Engine | ⏳ Запланирован | |
| Telegram Monitor | ⏳ Запланирован | |
| WhatsApp Monitor | ⏳ Запланирован | |
| extella Integration | ⏳ Запланирован | |
| UI / Tray | ⏳ Запланирован | |
| Report Generator | ⏳ Запланирован | |

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
