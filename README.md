# EU5Statistics

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/type--checked-mypy-blue.svg)](https://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-94%20passed-brightgreen.svg)]()
[![EU5 Version](https://img.shields.io/badge/EU5-1.4.*-blue.svg)](https://www.paradoxinteractive.com/games/europa-universalis-v)

**English** | [Русский](README.ru.md)

A tool for collecting and analyzing statistics from
[Europa Universalis V](https://www.paradoxinteractive.com/games/europa-universalis-v) save files.
It parses saves in real time, extracts data on population, cultures, religions, and vassalage,
stores it in PostgreSQL, and exposes SQL functions for analytics.

## Features

- 📊 **Real-time save parsing** — `watchdog` monitors the save folder and processes new files automatically.
- 🗄️ **PostgreSQL storage** — time-series support (data by year), idempotent processing (re-parsing replaces data for the year).
- 🌍 **Mod support** — automatically detects active mods from `playsets.json` and layers their localizations over vanilla.
- 📈 **SQL functions for analytics** — dynamics of cultures, religions, vassals, statistics by locations and countries.
- 📦 **Materialized views** — fast queries for Excel/VBA and BI tools integration.
- 🔄 **Error resilience** — failed files are copied to `data/errors/`, originals are preserved.
- 🌐 **Multilingual** — Russian and English localizations, extendable via `transformations.py`.

## Requirements

- **Python 3.12+**
- **PostgreSQL 14+**
- **[rakaly](https://github.com/crschnick/pdx_unlimiter/tree/master/rakaly)** —
  a CLI utility for converting binary Paradox saves to JSON.
  The `pdx_unlimiter` fork is recommended (tested and more stable).
- **Installed Europa Universalis V game** (tested on version **1.4.x**). Save file structure may change in future patches.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/EArboles/EU5Statistic.git
cd EU5Statistic
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e .
# For development (tests, linters):
pip install -e ".[dev]"
```

### 4. Configure `.env`

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
# Windows:
copy .env.example .env
```

Required variables:

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/eu5statistic` |
| `GAME_FOLDER` | Path to the `game` folder of EU5 installation | `C:/Steam/steamapps/common/Europa Universalis V/game` |
| `RAKALY_PATH` | Path to the rakaly executable (if not in PATH) | `C:/tools/rakaly/rakaly.exe` |

Optional variables:

| Variable | Description | Default |
|---|---|---|
| `USER_DATA_FOLDER` | Paradox profile folder (auto-detected) | `~/Documents/Paradox Interactive/Europa Universalis V` |
| `DATA_DIR` | Application data folder | `./data` |
| `INITIAL_YEAR` | Starting year for processing | `1337` |
| `PERIOD_SIZE` | Processing interval (years) | `5` |
| `SQL_ECHO` | Log SQL queries | `false` |

### 5. Apply migrations

```bash
alembic upgrade head
```

The command applies all migrations in order:

1. `***_initial_schema.py` — creates tables.
2. `***_add_custom_functions_and_materialized_.py` — creates
   SQL functions and the `location_stats_view` materialized view
   (via `alembic_utils`).
3. `***_add_index_on_location_stats_view.py` — creates indexes
   on `location_stats_view`. **This migration is written manually**
   because `alembic_utils` does not support index management for materialized views.

All three migrations are applied with a single `alembic upgrade head` command.

## Usage

### Watch mode (default)

```bash
eu5statistic
```

The program monitors the save folder (`USER_DATA_FOLDER/save games`)
and processes new files automatically. Press `Ctrl+C` to stop.

### Process a single file

```bash
eu5statistic --file path/to/save.eu5
```

Useful for debugging.

### Processing the save folder

```bash
eu5statistic --folder path/to/folder
```

Useful for batch processing.

### Clear localization cache

```bash
eu5statistic --clear-cache
```

The localization cache is stored in `data/cache/localization_cache.json` and
is invalidated automatically when files change. Use this flag if you suspect
the cache is stale.

### Example SQL queries

```sql
-- Population dynamics by religion for 1337–1500
SELECT * FROM get_religion_statistics(1337, 1500);

-- Country summary: population, % of primary culture, number of locations
SELECT * FROM get_country_summary(1337, 1500)
WHERE country_name LIKE '%Moscow%';

-- All vassals of a country (recursive)
SELECT c.localization_name
FROM get_all_vassals('MOS', 1444) v
JOIN countries c ON c.id = v.vassal_id;

-- World location statistics
SELECT * FROM get_world_location_stats(1337, 1500) LIMIT 20;
```
> **Note:** `country_name` comes from localization, so it depends on the
> selected language (`LOCALIZATION_LANGUAGE`). The country tag (`MOS`) is
> not used in the functions — only in `get_all_vassals`.

### Using SQL functions directly

You can build reports in any BI tool
(pgAdmin, DBeaver, Metabase, Power BI) — all functions are available via SQL:

```sql
SELECT * FROM get_country_summary(1337, 1500);
SELECT * FROM get_culture_statistics(1337, 1500);
SELECT * FROM get_religion_statistics(1337, 1500);
SELECT * FROM get_all_vassals('MOS', 1444);
```

## Screenshots

### Save processing

![Save processing](docs/screenshots/processing.png)

*Example output when processing a single file: mod loading, warnings, final status.*

### SQL query

![SQL query](docs/screenshots/sql_query.png)

*Result of `get_country_summary` in pgAdmin.*

## Excel Reports (XLSM)

The project consists of two parts:

1. **Python parser** (this repository) — processes saves and stores data in PostgreSQL.
2. **Excel file with macros (XLSM)** — connects directly to the database and generates ready-to-use analytical reports.

### XLSM Features:
* 🌍 **Global reports**: religions, cultures, locations, and countries.
* 🏳️ **Country-based reports**: selection of multiple tags (resolves issues like changing tags from "Moscow" to "Russia").
* 🌐 **Full localization**: built-in language selection (RU/EN); adding new languages ​​is easy.
* 🔌 **Smart connection**: automatic check for the presence of the PostgreSQL ODBC driver.
* 📊 **Visualization**: formulas, grouping, and conditional formatting within reports.

👉 **[Read the full XLSM Guide (English)](docs/XLSM_GUIDE.md)** | **[Подробное руководство по XLSM (Русский)](docs/XLSM_GUIDE.ru.md)**

## Mods

The project automatically detects **active** mods from `playsets.json`
in the player profile folder (`USER_DATA_FOLDER`). Only mods enabled
in the active playset (`isActive: true`) are considered.

Localizations are layered in the order of `orderedListMods`:
- The first mod in the list has the **lowest** priority.
- The last mod — the **highest** (overrides previous ones).

If a mod lacks localization for the selected language, a warning is printed
and the mod is skipped.

## Architecture

```
src/eu5statistic/
├── core/               # Parsing and localization
│   ├── binary_converter.py   # rakaly → JSON
│   ├── json_parser.py        # Streaming parser (ijson)
│   ├── mods_resolver.py      # Active mods from playsets.json
│   ├── entities/             # Dataclass models
│   └── localization/         # Cache, parser, loader, transformations
├── db/                 # PostgreSQL interaction
│   ├── models.py             # SQLModel models
│   ├── db_operations.py      # Upsert functions
│   ├── db_updater.py         # Load orchestration
│   ├── functions.py          # SQL functions and View
│   └── migrations/           # Alembic migrations
├── services/           # Orchestration
│   ├── file_processor.py     # Single file processing
│   ├── watcher.py            # Folder monitoring
│   └── logging_setup.py      # Logging
├── config.py           # Configuration from .env
└── main.py             # Entry point
```

**Processing pipeline:**

1. `watcher` catches a new `.eu5` file (event `on_moved`: `.tmp` → `.eu5`).
2. Waits for the file size to stabilize (2 checks with 1 sec interval).
3. `FileProcessor` converts `.eu5` → `.json` via rakaly.
4. `JsonParser` streams the JSON (ijson) and extracts data.
5. `DbUpdater` updates reference tables, clears data for the year, and inserts new data.
6. Successful files are copied to `data/processed/`, errors — to `data/errors/`.

**Step-by-step log (`detail_*.log`):**

![Detail log](docs/screenshots/detail_log.png)

*Every processing stage is logged with millisecond precision, making it easy to diagnose bottlenecks.*

**Key design decisions:**

- **Originals are never deleted** — autosaves and player saves stay in place,
  copies go to `processed/` and `errors/`. This protects against data loss.
- **Idempotency** — `clear_year_data(year)` before insertion allows re-processing
  a save for the same year without duplicates.
- **Stateless `FileProcessor`** — one instance per file, no races between
  parallel processing.

## Limitations

- Only **one active playset** is supported (the first with `isActive: true`).
- Mod localization is layered in the order of `orderedListMods` but **does not**
  take `dlc_load.json` into account (if present).
- **Network folders** are not supported (uses `PollingObserver`,
  but lock issues may occur).
- **No web interface** — only SQL functions and console output.
- **PostgreSQL only** — due to `ON CONFLICT` and materialized views.
  SQLite is not supported.
- **Game version compatibility**: tested on EU5 **1.4.x**. Future patches may alter the save file structure, requiring parser updates.

## FAQ

**A file is not being processed. What should I do?**
Check:
1. `WATCH_DIR` exists and matches the EU5 save folder.
2. `RAKALY_PATH` points to the executable (or rakaly is in `PATH`).
3. Logs in `data/logs/brief.log` and `data/logs/detail_*.log`.

**How do I add a new language?**
Add a function in `transformations.py` (following `transform_culture_name`)
and make sure the localization for the language exists in
`GAME_FOLDER/main_menu/localization/`. Then set the language in the game —
`LOCALIZATION_LANGUAGE` will be detected automatically from `pdx_settings.json`.

**Can I use SQLite?**
No. The project uses `ON CONFLICT` (PostgreSQL) and materialized views.
SQLite would require rewriting `db_operations.py` and `functions.py`.

**A save was processed with an error — where do I look for the cause?**
See `data/errors/` (copy of the file) and `data/logs/detail_*.log` (detailed log).
The cause is in the filename: `{reason}_{year}_{original}.eu5`.

## Contributing

1. Fork the repository.
2. Create a branch: `git checkout -b feature/my-feature`.
3. Ensure `ruff check .`, `mypy src/`, `pytest` pass without errors.
4. Commit: `git commit -m "Add my feature"`.
5. Push: `git push origin feature/my-feature`.
6. Open a Pull Request.

## Development

### Linting and formatting

```bash
ruff check .
ruff format .
```

### Type checking

```bash
mypy src/
```

### Tests

```bash
pytest
pytest --cov=eu5statistic --cov-report=html
```

**94 tests**, coverage of key modules:

| Module | Coverage |
|---|----------|
| `transformations.py` | 100%     |
| `models.py` | 100%     |
| `mods_resolver.py` | 100%     |
| `db_operations.py` | 100%     |
| `cache.py` | 93%      |
| `file_parser.py` | 100%     |
| `loader.py` | 89%      |
| `json_parser.py` | 91%      |
| `logging_setup.py` | 88%      |

Overall coverage — **64%**. The rest is integration tests with PostgreSQL and rakaly.

## License

MIT — see [LICENSE](LICENSE).

## Credits

- [rakaly](https://github.com/rakaly/cli) — original conversion utility.
- [pdx_unlimiter/rakaly](https://github.com/crschnick/pdx_unlimiter) — fork
  used in this project.
- [Paradox Interactive](https://www.paradoxinteractive.com/) — for the game.