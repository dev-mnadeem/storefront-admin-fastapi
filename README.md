# Storefront Admin API

Admin backend for a small shop: the catalogue, stock on hand, sales, and the
revenue figures an admin dashboard shows on its first screen. It is an async
FastAPI service on SQLAlchemy 2, deployed against MySQL 8.4 and tested
against SQLite.

The part worth reading is how a sale is recorded. Pricing the sale, taking
the units out of stock and writing the stock-movement log happen in one
transaction, and the stock is decremented with a conditional `UPDATE`, so two
requests racing for the last unit produce one sale and one `409`, never a
negative stock level.

## Run it

With Docker, from a fresh clone:

```bash
docker compose up --build -d          # MySQL 8.4 + the API on http://localhost:7111
docker compose exec api python -m demo_data   # 4 products, opening stock, 5 sales
curl http://localhost:7111/health
```

Swagger UI is at http://localhost:7111/docs. Compose reads optional overrides
from `.env` (copy `.env.example`): `API_PORT`, `DB_PORT`, the MySQL
credentials, and `ADMIN_API_KEY`. Stop and wipe the database with
`docker compose down -v`.

Without Docker, Python 3.12 (see `.python-version`) and a local SQLite file
are enough:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m demo_data
uvicorn app.main:app --reload         # http://localhost:8000
```

`DATABASE_URL` switches the database, for example
`mysql+aiomysql://storefront:storefront@localhost:7113/storefront_admin` to
use the Compose MySQL from the host.

## What it does

| Area | Endpoints |
| --- | --- |
| Products | `POST /products/`, `GET /products/` (search, category, `is_active`, paging), `GET` / `PATCH` / `DELETE /products/{id}` |
| Inventory | `GET /inventory/` (optionally only low stock), `POST /inventory/` to open stock, `PATCH /inventory/{product_id}` to adjust with a reason, `GET /inventory/logs/{product_id}` |
| Sales | `POST /sales/`, `GET /sales/` (date range, product, category), `GET /sales/export.csv` with the same filters |
| Reports | `GET /sales/summary` by day, ISO week, month or year; `GET /sales/summary_by_category`; `GET /sales/compare` (this period so far against the whole previous one) |
| Briefing | `GET /insights/`: a headline and bullets written from the same figures, which are returned alongside |
| Health | `GET /health` runs `SELECT 1` against the database |

Deleting a product only sets `is_active` to false, so past sales still
resolve; inactive products cannot be sold. List endpoints return
`{items, total, limit, offset}` and every error has the same shape:
`{"error": {"code", "message", "details"}}`.

## Examples

Recorded against `mysql:8.4` after seeding, with `ADMIN_API_KEY` set. The
full set of 15 exchanges is in [`docs/api-examples.json`](docs/api-examples.json).

Writes need the key once one is configured:

```http
POST /products/
{"name": "Pour-over kettle", "category": "Brewing", "price": "42.50"}

401 {"error": {"code": "unauthorized", "message": "Missing or invalid X-API-Key header.", "details": {}}}
```

With `X-API-Key`, the product is created, stocked with 3 units, and a sale of
2 is priced from the product:

```http
POST /sales/
{"product_id": 5, "quantity_sold": 2, "sale_date": "2026-11-02"}

201 {"product_id": 5, "quantity_sold": 2, "sale_date": "2026-11-02", "id": 6, "total_amount": "85.00"}
```

Selling 2 more is refused and leaves nothing behind:

```http
409 {"error": {"code": "conflict", "message": "Only 1 unit(s) of product 5 in stock.",
     "details": {"product_id": 5, "on_hand": 1, "requested": 2}}}
```

The stock log explains the level:

```http
GET /inventory/logs/5

200 {"items": [
       {"id": 11, "product_id": 5, "quantity_change": -2, "reason": "sale 6 on 2026-11-02", "created_at": "2026-11-08T16:42:57"},
       {"id": 10, "product_id": 5, "quantity_change": 3, "reason": "first delivery", "created_at": "2026-11-08T16:42:57"}],
     "total": 2, "limit": 50, "offset": 0}
```

Reports:

```http
GET /sales/summary?interval=week&start_date=2026-10-01

200 [{"period": "2026-W40", "revenue": "159.92"},
     {"period": "2026-W44", "revenue": "9.99"},
     {"period": "2026-W45", "revenue": "444.83"}]

GET /sales/compare?interval=month&on=2026-11-08

200 {"interval": "month", "current_period_start": "2026-11-01", "previous_period_start": "2026-10-01",
     "current_period_revenue": "454.82", "previous_period_revenue": "159.92", "change_percent": 184.4}
```

And the briefing (metrics trimmed):

```http
GET /insights/?interval=month&on=2026-11-08

200 {"provider": "rules",
     "headline": "Revenue so far this month is 454.82, up 184.40% on the previous month (159.92).",
     "bullets": ["Revenue by category: Gadgets 359.83, Brewing 85.00, Tools 9.99.",
                 "3 product(s) below the low-stock threshold of 10: Gizmo Y (0), Pour-over kettle (1), Gizmo X (4)."],
     "metrics": {"as_of": "2026-11-08", "current_period_revenue": 454.82, "low_stock_threshold": 10, ...}}
```

## How it is put together

```mermaid
flowchart LR
    R[Routers<br/>app/api/routers] --> S[Services<br/>app/services]
    S --> Repo[Repositories<br/>app/repositories]
    Repo --> DB[(MySQL / SQLite)]
    S --> AI[Briefing writers<br/>app/ai]
    Repo --> P[Period expressions<br/>per SQL dialect]
```

- Routers only parse input and shape output. Services own the business rules
  and decide when a transaction commits; repositories hold every SQL
  statement and only flush.
- Domain errors (`NotFoundError`, `ConflictError`, ...) are raised by services
  and turned into the common error body in one place, `app/core/errors.py`.
- Grouping by day, week, month or year has no portable SQL, so each dialect
  registers its own expressions in `app/repositories/periods.py`. Weeks are
  ISO 8601 weeks everywhere (`2025-W01` starts on Monday 2024-12-30), which is
  what lets the SQLite test suite check the labels MySQL returns.
- Request models carry the column limits (`DECIMAL(10,2)` for money, `INT`
  for unit counts), so an oversized value is a `422` instead of a database
  error.
- The CSV export prefixes names that start with `=`, `+`, `-` or `@` with an
  apostrophe so a spreadsheet does not run them as formulas.

### Recording a sale

```mermaid
sequenceDiagram
    participant C as Admin client
    participant A as Sale service
    participant D as Database
    C->>A: POST /sales/
    A->>D: UPDATE inventory SET quantity = quantity - n WHERE quantity - n >= 0
    alt one row updated
        A->>D: INSERT sale + inventory log
        A->>D: COMMIT
        A-->>C: 201 sale
    else no row updated
        A->>D: ROLLBACK
        A-->>C: 409 conflict
    end
```

`tests/test_stock_concurrency.py` holds two independent sessions at the same
point and checks the outcome: one sale, one conflict, one stock movement, zero
units left.

### Schema

Four tables. The models in `app/models/` create them on startup with
`create_all`; [`schema.sql`](schema.sql) is the readable MySQL DDL.

![Entity relationship diagram: products with inventory, sales and inventory_logs](ERD.png)

New databases get a `CHECK (quantity >= 0)` constraint on `inventory`.
`create_all` does not alter existing tables, so an older MySQL 8.0.16+
database needs [`migrations/001_inventory_nonnegative.sql`](migrations/001_inventory_nonnegative.sql)
after a backup and after fixing any negative rows. The conditional update
protects the API either way.

## Configuration

All settings are optional; `.env.example` documents each one.

| Variable | Default | Effect |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./storefront_admin.db` | Any async SQLAlchemy URL |
| `ADMIN_API_KEY` | unset | When set, `POST`/`PATCH`/`DELETE` require it in `X-API-Key`. Unset means open writes, and the API logs a warning at startup |
| `LOW_STOCK_THRESHOLD` | `10` | Below this a product counts as low stock |
| `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE` | `50`, `200` | Paging limits |
| `SQL_ECHO` | `false` | Log every statement |
| `INSIGHT_PROVIDER` | `rules` | `rules` or `anthropic` |

The default briefing writer is rule-based: deterministic, offline, no key.
`INSIGHT_PROVIDER=anthropic` with `ANTHROPIC_API_KEY` set and
`pip install -r requirements-ai.txt` hands the same figures to the Anthropic
Messages API (`ANTHROPIC_MODEL`, default `claude-opus-5`) and asks it only to
phrase them. A missing key, a missing package or any API error falls back to
the rule-based text, so `/insights/` always answers. The test suite covers that
provider with a fake SDK and never calls the API.

## Tests and lint

```bash
python -m pytest        # 88 tests, in-memory SQLite plus one file-backed race test
ruff check . && ruff format --check .
```

The same commands run inside Docker without a local Python:

```bash
docker run --rm -v "$PWD":/src:ro -w /work python:3.12-slim sh -c \
  'cp -a /src/. /work && pip install -q -r requirements-dev.txt && python -m pytest -q && ruff check .'
```

## Not done yet

- Migrations are hand-written SQL; there is no Alembic history.
- Sales cannot be refunded or corrected once recorded.
- The CSV export is built in memory before it is sent.

## License

MIT, see [LICENSE](LICENSE).
