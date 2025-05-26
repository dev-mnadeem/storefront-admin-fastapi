# Storefront Admin API

Admin backend for a small shop: products, stock levels, sales and revenue reports. It runs on FastAPI with async SQLAlchemy. MySQL is the intended database, and if `DATABASE_URL` isn't set it falls back to a local SQLite file so you can try it without installing anything.

Recording a sale prices it from the product, takes the quantity out of inventory and writes an inventory log entry, all in a single transaction. If there isn't enough stock you get a 409 with the on-hand and requested quantities.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m demo_data          # seeds a few products, stock and sales
uvicorn app.main:app --reload
```

Swagger docs are at http://localhost:8000/docs and `GET /health` also checks the database connection.

To use MySQL, copy `.env.example` to `.env` and set `DATABASE_URL` (for example `mysql+aiomysql://...`).

## Endpoints

- Products: `POST /products/`, `GET /products/` (search, category, is_active, paging), `GET`, `PATCH`, `DELETE /products/{product_id}` (delete is soft, it sets `is_active` to false)
- Inventory: `GET /inventory/` (with low-stock filtering), `POST /inventory/`, `PATCH /inventory/{product_id}` for adjustments with a reason, `GET /inventory/logs/{product_id}`
- Sales: `POST /sales/`, `GET /sales/` with date, product and category filters, `GET /sales/export.csv`
- Reports: `GET /sales/summary` (by day, week, month or year), `GET /sales/summary_by_category`, `GET /sales/compare` (current period against the previous one)
- `GET /insights/` returns a short text summary of revenue and low stock plus the raw numbers

List endpoints return `{items, total, limit, offset}`. Errors come back as `{"error": {"code", "message", "details"}}`.

The schema is four tables (products, inventory, sales, inventory_logs). It's created with `create_all` on startup, and `schema.sql` and `ERD.png` document it.

## Configuration

Everything is optional, see `.env.example`. Useful ones: `ADMIN_API_KEY` (if set, write requests need an `X-API-Key` header), `LOW_STOCK_THRESHOLD`, `DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`, `SQL_ECHO`.

`/insights/` uses a rule-based text generator by default. Setting `INSIGHT_PROVIDER=anthropic` with `ANTHROPIC_API_KEY` (and installing `requirements-ai.txt`) uses the Anthropic API to write the text instead, and it falls back to the rules if that fails.

## Tests

```bash
pytest
ruff check .
```

Tests run on in-memory SQLite, no MySQL needed.

## TODO

- Add migrations instead of relying on `create_all`
- Support refunds or corrections for sales
- Stream the CSV export instead of building it in memory
