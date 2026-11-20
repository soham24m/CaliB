# CaliB Business Analytics

A responsive business intelligence dashboard for the supplied CaliB Foods order line dataset. React and Recharts provide the client; FastAPI serves parameterized DuckDB aggregations and paginated transaction data.

The sidebar brand uses the supplied California Burrito logo at `public/images/logo.png`, served locally with the app.

## Stack and architecture

- **Client:** React 19, TypeScript, Vite, Recharts, Lucide React.
- **API:** Python 3.10+, FastAPI, Uvicorn.
- **Analytics store:** DuckDB, a local embedded columnar database well suited to analytical scans without requiring a separately operated database server.
- **Ingestion:** pandas/openpyxl reads the source workbook once, validates required columns, normalizes timestamps and numeric values, drops unusable rows, calculates `Line_Revenue`, then persists the result in `backend/data/calib.duckdb`.
- **Data flow:** browser filters → API query parameters → parameterized DuckDB SQL → compact aggregate or page of rows. The browser never receives the full source dataset.

## Calculations and assumptions

Each row is an order line. Line revenue is `Price × Quantity`; revenue is the sum of line revenue; orders are `COUNT(DISTINCT BillNo)`; units are summed quantity; AOV is revenue divided by distinct bills; records count valid ingested lines. Invalid timestamps, prices, quantities, and missing bills are excluded; negative price or quantity lines are excluded. Other optional dimensions are retained as nullable strings. No comparison-period metric is shown because no previous-period comparison has been independently specified.

Filters combine using AND and are applied on the backend. Date boundaries are inclusive calendar dates. Product category is the source `Group` field. Search matches bill, item, and outlet. Transaction paging is capped at 100 rows per response. CSV export returns all matching rows and should be used with appropriately selective filters on very large selections.

## API

- `GET /api/health` — status, valid record count, distinct bills, date bounds.
- `GET /api/filters` — dimensions and dataset date range.
- `GET /api/overview` — KPIs, daily revenue trend, order type mix, top outlet snapshot.
- `GET /api/revenue?granularity=day|week|month` — trend and revenue breakdowns.
- `GET /api/categories` — category revenue, units, and bills.
- `GET /api/products?sort=revenue|quantity|name&limit=100` — product metrics and category revenue/unit summaries.
- `GET /api/outlets` — outlet comparison and leading category.
- `GET /api/orders?page=1&page_size=25&search=...` — paginated line items.
- `GET /api/export` — CSV of all matching line items.

All analytical endpoints accept `start`, `end`, `outlet`, `category`, `order_type`, `settlement`, and `brand` where relevant. API docs are at `/docs`.

## Install and run locally

Requirements: Node 20+, Python 3.10+, and the workbook.

```sh
npm install
python3 -m pip install -r backend/requirements.txt
```

The default source path is `/Users/sohamsiddharthamishra/Downloads/data.xlsx`. Set `CALIB_EXCEL=/path/to/data.xlsx` to use another copy. Start the API (first start ingests the workbook):

```sh
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Build the client once, then start the API. The API serves both the built frontend and `/api` routes from one origin:

```sh
npm run build
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000`. Interactive API docs are at `http://localhost:8000/docs`. For frontend-only development with hot reload, `npm run dev` uses Vite’s proxy to the API. Use `CALIB_DB` to select a different DuckDB file. The database is generated locally and excluded from Git.

## Project structure

```text
backend/main.py       ingestion and analytics API
backend/requirements.txt
src/main.tsx          dashboard screens and data interactions
src/style.css         responsive product styling
vite.config.ts        local API proxy
```

## Performance and deployment

Aggregations and filters execute in DuckDB; only chart aggregates, option lists, and a bounded transaction page are sent to the client. Workbook ingestion occurs once when the database table is absent. For deployment, build the client with `npm run build`, host `dist/` behind a static server, and run the FastAPI service with a persistent writable DuckDB path and configured workbook path. Update CORS origins to the deployed frontend domain and place both behind HTTPS/reverse proxy as appropriate. This local assessment build does not include authentication, scheduled refresh, or cloud deployment configuration.

## Validation status

The dashboard uses the supplied workbook path by default. On first API startup it logs the number of valid lines ingested; `/api/health` exposes line count, distinct bills, and date bounds for reconciliation. See `TECHNICAL_DECISIONS.md` for implementation trade-offs.


## Design Decisions

The dashboard uses a restricted California Burrito palette: red and deep red for brand emphasis, forest green for ink and chart structure, and cream for the page canvas. The official logo is served locally. The restricted series colors keep data views visually tied to the brand. Gabarito provides the brand's bold display style and is bundled locally with its OFL license; the 700 weight is preloaded. Contrast values and exceptions are documented in [design_notes.md](docs/design_notes.md); deep red is used for small cream text on red surfaces, while cream-on-red is reserved for bold large text.

Responsive render captures are stored in `docs/screenshots/` at desktop (1440px), tablet (768px), and mobile (390px) widths.

The dashboard includes an About section with Soham Siddhartha Mishra’s supplied photo, profile, education, and listed skills. The footer credits him for the design and build.
