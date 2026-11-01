# EU5Statistics

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type--checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-90%20passed-brightgreen.svg)]()

[English](README) | **Русский**)

Инструмент для сбора и анализа статистики из сохранений
[Europa Universalis V](https://www.paradoxinteractive.com/games/europa-universalis-v).
Парсит сохранения в реальном времени, извлекает данные о населении, культурах,
религиях и вассалитете, складывает в PostgreSQL и предоставляет SQL-функции
для аналитики.

## Возможности

- 📊 **Парсинг сохранений в реальном времени** — `watchdog` отслеживает папку
  с сохранениями и обрабатывает новые файлы автоматически.
- 🗄️ **Хранение в PostgreSQL** — поддержка временных рядов (данные по годам),
  идемпотентная обработка (повторный парсинг заменяет данные за год).
- 🌍 **Поддержка модов** — автоматически определяет активные моды из
  `playsets.json` и накладывает их локализации поверх ванильных.
- 📈 **SQL-функции для аналитики** — динамика культур, религий, вассалов,
  статистика по локациям и странам.
- 📦 **Материализованные представления** — быстрые запросы для интеграции
  с Excel/VBA и BI-инструментами.
- 🔄 **Устойчивость к ошибкам** — файлы с ошибками копируются в `data/errors/`,
  оригиналы сохраняются.
- 🌐 **Мультиязычность** — русская и английская локализации, расширяемая
  через `transformations.py`.

## Требования

- **Python 3.12+**
- **PostgreSQL 14+**
- **[rakaly](https://github.com/crschnick/pdx_unlimiter/tree/master/rakaly)** —
  CLI-утилита для конвертации бинарных сохранений Paradox в JSON.
  Рекомендуется форк от `pdx_unlimiter` (проверенный, работает стабильнее).
- **Установленная игра Europa Universalis V** (для доступа к локализациям
  и папке сохранений).

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/EArboles/EU5Statistic.git
cd EU5Statistic
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -e .
# Для разработки (тесты, линтеры):
pip install -e ".[dev]"
```

### 4. Настройка `.env`

Скопируйте `.env.example` в `.env` и заполните значения:

```bash
cp .env.example .env
# Windows:
copy .env.example .env
```

Обязательные переменные:

| Переменная | Описание | Пример |
|---|---|---|
| `DATABASE_URL` | Строка подключения к PostgreSQL | `postgresql+asyncpg://user:pass@localhost:5432/eu5statistic` |
| `GAME_FOLDER` | Путь к папке `game` установленной EU5 | `C:/Steam/steamapps/common/Europa Universalis V/game` |
| `RAKALY_PATH` | Путь к исполняемому файлу rakaly (если не в PATH) | `C:/tools/rakaly/rakaly.exe` |

Опциональные:

| Переменная | Описание | По умолчанию |
|---|---|---|
| `USER_DATA_FOLDER` | Папка профиля Paradox (автоопределение) | `~/Documents/Paradox Interactive/Europa Universalis V` |
| `DATA_DIR` | Папка для данных приложения | `./data` |
| `INITIAL_YEAR` | Год начала обработки | `1337` |
| `PERIOD_SIZE` | Периодичность обработки (лет) | `5` |
| `SQL_ECHO` | Логировать SQL-запросы | `false` |

### 5. Применение миграций

```bash
alembic upgrade head
```

Команда применяет все миграции по порядку:

1. `***_initial_schema.py` — создание таблиц.
2. `***_add_custom_functions_and_materialized_.py` — создание
   SQL-функций и материализованного представления `location_stats_view`
   (через `alembic_utils`).
3. `***_add_index_on_location_stats_view.py` — создание индексов
   на `location_stats_view`. **Эта миграция написана вручную**, потому что
   `alembic_utils` не поддерживает управление индексами для materialized views.

Все три миграции применяются одной командой `alembic upgrade head`.

## Использование

### Режим наблюдения (по умолчанию)

```bash
eu5statistic
```

Программа отслеживает папку сохранений (`USER_DATA_FOLDER/save games`)
и автоматически обрабатывает новые файлы. Остановка — `Ctrl+C`.

### Обработка одного файла

```bash
eu5statistic --file path/to/save.eu5
```

Полезно для отладки или пакетной обработки.

### Очистка кеша локализаций

```bash
eu5statistic --clear-cache
```

Кеш локализаций хранится в `data/cache/localization_cache.json` и
инвалидируется автоматически при изменении файлов. Флаг нужен, если
вы подозреваете, что кеш устарел.

### Пример SQL-запроса

```sql
-- Динамика популяции по религиям за 1337–1500
SELECT * FROM get_religion_statistics(1337, 1500);

-- Сводка по странам: население, % основной культуры, число локаций
SELECT * FROM get_country_summary(1337, 1500)
WHERE country_name LIKE '%Моск%';

-- Все вассалы страны (рекурсивно)
SELECT c.localization_name
FROM get_all_vassals('MOS', 1444) v
JOIN countries c ON c.id = v.vassal_id;

-- Статистика по локациям мира
SELECT * FROM get_world_location_stats(1337, 1500) LIMIT 20;
```
> **Примечание:** `country_name` берётся из локализации, поэтому зависит
> от выбранного языка (`LOCALIZATION_LANGUAGE`). Тег страны (`MOS`) в
> функциях не используется — только в `get_all_vassals`.

## Примеры

### Обработка сохранения

![Обработка сохранения](docs/screenshots/processing.png)

*Пример вывода при обработке одного файла: загрузка модов, предупреждения, итоговый статус.*

### SQL-запрос

![SQL-запрос](docs/screenshots/sql_query.png)

*Результат выполнения `get_country_summary` в pgAdmin*

## Excel-отчёты (XLSM)

Проект состоит из двух частей:

1. **Python-парсер** (этот репозиторий) — обрабатывает сохранения и
   складывает данные в PostgreSQL.
2. **Excel-файл с макросами (XLSM)** — использует SQL-функции из
   `functions.py` для генерации готовых отчётов: динамика населения,
   культур, религий, вассальных отношений.

> ⚠️ **Статус:** XLSM-часть находится в активной разработке. Python-часть
> полностью функциональна и предоставляет все необходимые SQL-функции.
> Готовый XLSM будет опубликован отдельно (или добавлен в `docs/`).

### Какие отчёты планируются

- **Динамика населения** по странам, культурам, религиям за выбранный период.
- **Вассальные сети** — иерархия сюзеренов и вассалов.
- **Сравнение культур** — доля культуры в стране, регионе, мире.
- **Карты плотности** — население и грамотность по локациям.

### Как использовать SQL-функции напрямую

Если XLSM ещё не готов, вы можете строить отчёты в любом BI-инструменте
(pgAdmin, DBeaver, Metabase, Power BI) — все функции доступны через SQL:

```sql
SELECT * FROM get_country_summary(1337, 1500);
SELECT * FROM get_culture_statistics(1337, 1500);
SELECT * FROM get_religion_statistics(1337, 1500);
SELECT * FROM get_all_vassals('MOS', 1444);
```

## Моды

Проект автоматически определяет **активные** моды из `playsets.json`
в папке профиля игрока (`USER_DATA_FOLDER`). Учитываются только моды,
включённые в активном плейсете (`isActive: true`).

Локализации накладываются в порядке `orderedListMods`:
- Первый мод в списке имеет **низший** приоритет.
- Последний мод — **высший** (перезаписывает предыдущие).

Если у мода нет локализации для выбранного языка — выводится предупреждение,
мод пропускается.

## Архитектура

```
src/eu5statistic/
├── core/               # Парсинг и локализация
│   ├── binary_converter.py   # rakaly → JSON
│   ├── json_parser.py        # Потоковый парсер (ijson)
│   ├── mods_resolver.py      # Активные моды из playsets.json
│   ├── entities/             # Dataclass-модели
│   └── localization/         # Кеш, парсер, загрузчик, трансформации
├── db/                 # Работа с PostgreSQL
│   ├── models.py             # SQLModel-модели
│   ├── db_operations.py      # Upsert-функции
│   ├── db_updater.py         # Оркестрация загрузки
│   ├── functions.py          # SQL-функции и View
│   └── migrations/           # Alembic-миграции
├── services/           # Оркестрация
│   ├── file_processor.py     # Обработка одного файла
│   ├── watcher.py            # Мониторинг папки
│   └── logging_setup.py      # Логирование
├── config.py           # Конфигурация из .env
└── main.py             # Точка входа
```

**Поток обработки:**

1. `watcher` ловит новый `.eu5` файл (событие `on_moved`: `.tmp` → `.eu5`).
2. Ждёт стабилизации размера файла (2 проверки по 1 сек).
3. `FileProcessor` конвертирует `.eu5` → `.json` через rakaly.
4. `JsonParser` потоково читает JSON (ijson), извлекает данные.
5. `DbUpdater` обновляет справочники, очищает данные за год и вставляет новые.
6. Успешные файлы копируются в `data/processed/`, ошибки — в `data/errors/`.

**Пошаговый лог (`detail_*.log`):**

![Detail лог](docs/screenshots/detail_log.png)

*Каждый этап обработки логируется с точностью до миллисекунд, что позволяет диагностировать узкие места.*

**Ключевые решения:**

- **Оригиналы не удаляются** — автосейвы и сейвы игрока остаются на месте,
  копии кладутся в `processed/` и `errors/`. Это защищает от потери данных.
- **Идемпотентность** — `clear_year_data(year)` перед вставкой позволяет
  повторно обрабатывать сейв за тот же год без дублей.
- **Stateless `FileProcessor`** — один экземпляр на файл, без гонок между
  параллельными обработками.

## Ограничения

- Поддерживается только **один активный плейсет** (первый с `isActive: true`).
- Локализация модов накладывается в порядке `orderedListMods`, но **не
  учитывает** `dlc_load.json` (если он есть).
- Не поддерживаются **сетевые папки** (используется `PollingObserver`,
  но могут быть проблемы с блокировками).
- **Нет веб-интерфейса** — только SQL-функции и консольный вывод.
- **Только PostgreSQL** — из-за `ON CONFLICT` и materialized views.
  SQLite не подходит.

## FAQ

**Файл не обрабатывается, что делать?**
Проверьте:
1. `WATCH_DIR` существует и совпадает с папкой сохранений EU5.
2. `RAKALY_PATH` указывает на исполняемый файл (или rakaly в `PATH`).
3. Логи в `data/logs/brief.log` и `data/logs/detail_*.log`.

**Как добавить новый язык?**
Добавьте функцию в `transformations.py` (по образцу `transform_culture_name`)
и убедитесь, что локализация для языка есть в `GAME_FOLDER/main_menu/localization/`.
Затем установите язык в игре — `LOCALIZATION_LANGUAGE` определится автоматически
из `pdx_settings.json`.

**Можно ли использовать SQLite?**
Нет. Проект использует `ON CONFLICT` (PostgreSQL) и materialized views.
Для SQLite потребуется переписать `db_operations.py` и `functions.py`.

**Сейв обработан с ошибкой — где искать причину?**
Смотрите `data/errors/` (копия файла) и `data/logs/detail_*.log` (подробный лог).
Причина в имени файла: `{reason}_{year}_{original}.eu5`.

## Contributing

1. Fork репозитория.
2. Создайте ветку: `git checkout -b feature/my-feature`.
3. Убедитесь, что `ruff check .`, `mypy src/`, `pytest` проходят без ошибок.
4. Коммит: `git commit -m "Add my feature"`.
5. Push: `git push origin feature/my-feature`.
6. Откройте Pull Request.

## Разработка

### Линтинг и форматирование

```bash
ruff check .
ruff format .
```

### Типизация

```bash
mypy src/
```

### Тесты

```bash
pytest
pytest --cov=eu5statistic --cov-report=html
```

**90 тестов**, покрытие ключевых модулей:

| Модуль | Покрытие |
|---|---|
| `transformations.py` | 100% |
| `models.py` | 100% |
| `mods_resolver.py` | 100% |
| `db_operations.py` | 100% |
| `cache.py` | 93% |
| `file_parser.py` | 92% |
| `loader.py` | 92% |
| `json_parser.py` | 91% |
| `logging_setup.py` | 88% |

Общее покрытие — **55%**. Остальное — интеграционные тесты с PostgreSQL и rakaly.

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Credits

- [rakaly](https://github.com/rakaly/cli) — оригинальная утилита конвертации.
- [pdx_unlimiter/rakaly](https://github.com/crschnick/pdx_unlimiter) — форк,
  используемый в проекте.
- [Paradox Interactive](https://www.paradoxinteractive.com/) — за игру.