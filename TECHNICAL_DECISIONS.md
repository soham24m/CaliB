# Technical decisions

- **DuckDB over a service database:** the deliverable is a single-user local analytics assessment with a 300K-row source. DuckDB provides SQL, persistence, and analytical scans without infrastructure setup.
- **Excel as an ingestion source, not a query source:** pandas/openpyxl are used at startup to validate and normalize the workbook; DuckDB is the queryable system of record for this app. The original workbook is preserved in place.
- **Line grain is explicit:** ingestion computes `Line_Revenue = Price * Quantity`; order KPIs count distinct `BillNo`, never rows. The transaction table remains at line-item grain.
- **Server-side filters and paging:** all dimensions combine in SQL predicates. Transaction search and pagination happen before serialization. Browser requests do not download the full table.
- **Nullable descriptive fields:** optional dimensions remain null and are displayed as unspecified/blank rather than fabricated. Rows that cannot participate in dated or monetary measures are removed.
- **No unsubstantiated comparisons:** the UI does not show period-over-period percentages because the required comparison window and treatment of partial periods were not defined.
- **Simple local deployment:** Vite proxies `/api` to FastAPI in development. A reverse proxy/static frontend plus one API process is enough for deployment; production CORS and durable storage must be configured for that host.
