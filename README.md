<div align="center">

# TruthOdds

### Платформа вероятностной оценки событий, калибровки аналитиков и мониторинга медиа

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-SQLAlchemy_2.0-003B57.svg?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC.svg?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Tests-30%2F30%20Passed-brightgreen.svg?style=flat-square&logo=pytest&logoColor=white)](#тестирование)
[![License](https://img.shields.io/badge/License-MIT-purple.svg?style=flat-square)](LICENSE)

*Система собирает прогнозы экспертов из мировых СМИ и соцсетей, оценивает их историческую точность через **Brier Score** (включая срез за 1 год) и рассчитывает объективную вероятность будущих событий на основе **Байесовской агрегации**.*

[Быстрый старт](#быстрый-старт) •
[Ключевые возможности](#ключевые-возможности) •
[Математический аппарат](#математический-аппарат) •
[Структура проекта](#структура-проекта) •
[API Документация](#api-эндпоинты) •
[Тестирование](#тестирование)

---

</div>

## Быстрый старт

### 1. Клонирование репозитория
```bash
git clone https://github.com/coolboy6969/truth-odds.git
cd truth-odds
```

### 2. Создание и активация виртуального окружения
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Запуск приложения
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

После старта перейдите в браузере:
* **Интерактивный дашборд:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Swagger API документация:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc спецификация:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Ключевые возможности

* **Радар кандидатов и живой поиск в медиа (`RealWorldAnalystDiscoveryService`)**: вертикальная поисковая система с бесконечной прокруткой, сканирующая Google News RSS и финансовые издания (Cointelegraph, CoinDesk, CNBC, Forbes, РБК) без платных API-ключей, извлекающая прогнозы реальных аналитиков и переводящая их в базу расчетов в один клик.
* **Поиск тем для оценки (`NarrativeCluster` + AI Consensus)**: поисковая лента верифицируемых рыночных тем с бесконечной прокруткой, автоматическим ИИ-описанием, аргументами «За / Против» и переводом темы в отслеживаемое событие.
* **Проверка точности аналитика за 1 год (`SpeakerAccuracy`)**: расчет персонального Brier Score и процента сбывшихся прогнозов за выбранный период (1 год, 6 месяцев, 90 дней, все время) с детальным журналом проверенных заявлений.
* **Автономный расчет вероятностей и Авто-Оракул (`AutoEventAnalysisEngine` & `AutoOracleService`)**: автоматическая категоризация новых прогнозов, семантическая дедупликация и фоновая сверка спотовых котировок Binance (BTC, ETH, SOL и др.) и дедлайнов с пересчетом рейтингов экспертов.

---

## Математический аппарат

1. **Персональный рейтинг аналитика (Brier Score)**:
   $$BS = \frac{1}{N} \sum_{i=1}^N (f_i - o_i)^2$$
   где $f_i \in [0.01, 0.99]$ — уверенность спикера, $o_i \in \{0, 1\}$ — фактический исход события (`0.00` — идеальная точность, `0.25` — случайное угадывание).

2. **Сглаживание веса доверия (Bayesian Shrinkage)**:
   $$W_i = \frac{M \cdot W_0 + N \cdot \text{RawCredibility}}{M + N}$$
   защищает модель от искажений при малом числе прогнозов ($W_0 = 0.5$, $M = 3$).

3. **Байесовская агрегация в логарифмических шансах (Log-Odds Aggregation)**:
   $$L_{\text{posterior}} = L_{\text{base}} + \sum_{i=1}^K w_i \cdot \left( L_i - L_{\text{base}} \right), \quad P_{\text{итог}} = \frac{1}{1 + e^{-L_{\text{posterior}}}}$$

---

## Архитектура системы

```mermaid
flowchart TD
    subgraph Sources["Внешние источники данных"]
        A1["Google News RSS (ru / en)"]
        A2["Cointelegraph & Financial RSS"]
        A3["Binance Spot Ticker (Live Prices)"]
    end

    subgraph Discovery["Модуль обнаружения (Discovery Engine)"]
        B1["RealWorldAnalystDiscoveryService"]
        B2["SpeakerDiscoveryEngine"]
        B3["SemanticEventMatcher"]
    end

    subgraph Core["Ядро TruthOdds"]
        D1["Радар кандидатов и Поиск тем"]
        D2["База аналитиков (Brier Score & 1Y Accuracy)"]
        D3["ForecasterScorer (Bayesian Log-Odds)"]
        D4["AutoOracleService (Price Targets & Deadlines)"]
    end

    A1 & A2 --> B1
    B1 & B2 --> D1
    D1 --> D2
    D2 & B3 --> D3
    A3 --> D4
    D4 --> D2
```

---

## Структура проекта

```text
ProjPlatf/
├── app/
│   ├── api/                    # REST API эндпоинты FastAPI
│   │   ├── discovery.py        # Радар кандидатов, поиск тем для оценки, ИИ-анализ
│   │   ├── events.py           # События, вероятности, ручное и авто-разрешение
│   │   ├── oracle.py           # Спотовые котировки Binance и проверка таргетов
│   │   ├── speakers.py         # Лидерборд аналитиков, проверка точности за 1 год
│   │   ├── statements.py       # Заявления и цитаты спикеров
│   │   ├── sources.py          # Источники данных
│   │   ├── crypto_seed.py      # Демо-данные авторов и событий
│   │   └── demo.py             # Сброс базы данных и демо-состояния
│   ├── database/               # Сессия SQLAlchemy и миграции SQLite
│   ├── discovery/              # Модули обнаружения и живого поиска в СМИ
│   ├── engine/                 # Brier Score, Shrinkage, Байесовская агрегация
│   ├── extractor/              # Извлечение прогнозов (LLM + эвристика)
│   ├── ingestion/              # Парсинг транскриптов и XML RSS
│   ├── models/                 # SQLAlchemy сущности (Speaker, Event, Statement, Candidate)
│   ├── oracles/                # Оракул Binance и парсер ценовых таргетов
│   ├── services/               # Бизнес-логика системы прогнозов
│   ├── templates/              # Интерфейс дашборда (Tailwind CSS)
│   ├── config.py               # Конфигурация Pydantic Settings
│   └── main.py                 # Точка входа приложения, настройки, фоновый воркер
├── tests/                      # Модульные и интеграционные тесты (Pytest)
├── requirements.txt            # Зависимости проекта
├── truth_odds.db               # База данных SQLite
└── README.md                   # Документация проекта
```

---

## Тестирование

Все ключевые математические формулы, алгоритмы извлечения, интеграции с медиа и оракулами покрыты автоматическими тестами:

```bash
python -m pytest tests/ -v
```

---

## API Эндпоинты

| Метод | Эндпоинт | Описание |
| :--- | :--- | :--- |
| `GET` | `/api/events` | Список отслеживаемых событий с Байесовскими вероятностями |
| `POST` | `/api/events` | Создать новое событие или задачу для анализа |
| `POST` | `/api/events/{id}/resolve` | Разрешить исход события (TRUE / FALSE) с обновлением Brier Score |
| `GET` | `/api/speakers?period=1y` | Список принятых аналитиков и их точность за выбранный период (`1y`, `6m`, `90d`, `all`) |
| `GET` | `/api/speakers/{id}/accuracy?period=1y` | Детальный отчет точности аналитика за период с историей прогнозов |
| `POST` | `/api/discovery/radar/search-person` | Живой поиск реального аналитика в мировых медиа |
| `POST` | `/api/discovery/radar/load-more` | Пагинация и бесконечная прокрутка радара кандидатов |
| `GET` | `/api/discovery/narratives` | Список тем для оценки с ИИ-описанием |
| `POST` | `/api/discovery/narratives/search` | Поисковая система тем для оценки и синтез проверяемых тем |
| `POST` | `/api/discovery/narratives/load-more` | Подгрузка новых тем для оценки при прокрутке вниз |
| `GET` | `/api/oracle/crypto-prices` | Текущие спотовые цены Binance (BTC, ETH, SOL и др.) |
| `POST` | `/api/oracle/trigger-check` | Принудительная сверка активных событий со спотовым оракулом |
| `GET` / `POST` | `/api/settings` | Чтение и сохранение параметров аналитической платформы |

---

## Переменные окружения (Опционально)

Платформа спроектирована по принципу **Zero-Config Local-First**: она полностью работоспособна сразу после установки без создания файла `.env` и без платных API-ключей. По умолчанию используются локальная база SQLite, встроенный эвристический NLP-экстрактор прогнозов, публичные RSS-потоки мировых СМИ и открытый спотовый API Binance.

Для тонкой настройки базы данных, подключения внешних языковых моделей (LLM) или изменения гиперпараметров Байесовского движка создайте файл `.env` в корневой директории проекта (`ProjPlatf/.env`). Конфигурация автоматически валидируется через `pydantic-settings` в модуле `app/config.py`.

### Пример полного файла `.env`

```env
# -----------------------------------------------------------------------------
# 1. ОСНОВНЫЕ ПАРАМЕТРЫ ПРИЛОЖЕНИЯ И БАЗЫ ДАННЫХ
# -----------------------------------------------------------------------------
# Отображаемое имя сервиса в метаданных FastAPI и OpenAPI (/docs)
APP_NAME="TruthOdds - Forecaster Accuracy & Event Probability Engine"

# Строка подключения SQLAlchemy.
# По умолчанию используется локальный файл SQLite в корне проекта.
# Для продакшена можно указать PostgreSQL: postgresql+psycopg2://user:password@localhost:5432/truthodds
DATABASE_URL="sqlite:///./truth_odds.db"

# -----------------------------------------------------------------------------
# 2. ИНТЕГРАЦИЯ С ЯЗЫКОВЫМИ МОДЕЛЯМИ (LLM EXTRACTION & ANALYSIS)
# -----------------------------------------------------------------------------
# Ключ Google Gemini API (используется для глубокого семантического разбора цитат,
# выделения скрытых условий прогноза и генерации аналитического описания тем).
GEMINI_API_KEY=""

# Ключ OpenAI API (альтернативный LLM-провайдер для извлечения структуры прогноза
# и оценки численной уверенности автора из неструктурированного текста).
OPENAI_API_KEY=""

# -----------------------------------------------------------------------------
# 3. ГИПЕРПАРАМЕТРЫ БАЙЕСОВСКОЙ МОДЕЛИ И КАЛИБРОВКИ (SCORING ENGINE)
# -----------------------------------------------------------------------------
# Базовая априорная вероятность (Prior Base Rate) для новых событий до учета мнений экспертов.
# Диапазон: от 0.05 до 0.95 (0.5 = нейтральные стартовые шансы 50/50).
DEFAULT_BASE_RATE=0.5

# Коэффициент сглаживания Байеса (Shrinkage Prior Sample Size, параметр M).
# Определяет количество "псевдонаблюдений", защищающих рейтинг от случайных угадываний
# у новых аналитиков с малой историей (1-2 сбывшихся прогноза).
PRIOR_SAMPLE_SIZE=3

# Начальный вес доверия (Default Prior Weight, параметр W_0) для новых аналитиков,
# у которых еще нет разрешенных прогнозов в базе. Диапазон: от 0.1 до 0.9.
DEFAULT_PRIOR_WEIGHT=0.5
```

### Подробное описание всех переменных

| Переменная | По умолчанию | Назначение |
| :--- | :--- | :--- |
| `APP_NAME` | `"TruthOdds"` | Системное имя сервиса в `/api/health` и заголовке документации (`/docs`). |
| `DATABASE_URL` | `"sqlite:///./truth_odds.db"` | Подключение к БД (SQLite из коробки; поддерживается переход на PostgreSQL). |
| `GEMINI_API_KEY` | `None` | Ключ Google Gemini для нейросетевого разбора сложных цитат (при отсутствии работает встроенный парсер). |
| `OPENAI_API_KEY` | `None` | Ключ OpenAI как альтернативный LLM-провайдер для анализа заявлений и тем. |
| `DEFAULT_BASE_RATE` | `0.5` | Стартовая (априорная) вероятность новых событий до учета мнений экспертов (`0.5` = 50%). |
| `PRIOR_SAMPLE_SIZE` | `3` | Коэффициент сглаживания Байеса (защита от завышения рейтинга при 1–2 случайных угадываниях). |
| `DEFAULT_PRIOR_WEIGHT` | `0.5` | Базовый вес доверия новым аналитикам до накопления истории **Brier Score**. |

> Если ключи `GEMINI_API_KEY` и `OPENAI_API_KEY` не указаны, система автоматически использует встроенный аналитический движок без потери функциональности.

---

## Лицензия

Проект распространяется под открытой лицензией [MIT License](LICENSE).
