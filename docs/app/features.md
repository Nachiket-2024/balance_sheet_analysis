# Features: Implementation Notes

See [Architecture](architecture/README.md) for the overall `app/`/`mystic_auth/` structure this fits into.

## LLM chat scope

`backend/app/llm/llm_service.py` grounds the chat by serializing a curated
set of key balance-sheet metrics (assets, liabilities, equity, debt,
liquidity) into the prompt sent to Groq, not the full ~68-field row, to keep
the prompt focused. yfinance's balance-sheet endpoint has no income-statement
fields, so "sales"/revenue growth (problem statement 1a) isn't available from
this data source; the chart and chat both cover what a balance sheet itself
reports (assets/liabilities/equity trends), not an income statement. Adding
income-statement ingestion is a natural next feature, structured the same
way (`backend/app/income_statements/`, mirroring `balance_sheets/`).

Both the LLM chat and balance-sheet import endpoints are rate-limited
(per-IP and per-account, via mystic_auth's `rate_limiter_service`) since each
call costs real money/quota against Groq or yfinance respectively.

## yfinance needs a browser-impersonating, timeout-bounded session

`backend/app/balance_sheets/balance_sheet_crud.py`'s `_fetch_balance_sheet_row_sync`
builds its own `curl_cffi.requests.Session(impersonate="chrome", timeout=15)`
and passes it to `yf.Ticker(ticker, session=...)`, rather than letting
yfinance construct its own default session. Two things forced this, both
non-obvious from yfinance's own docs:

- **No default timeout.** yfinance has no built-in request timeout at all:
  a hung/slow Yahoo response would tie up an `asyncio.to_thread` worker
  indefinitely, since this is the one blocking network call in the app run
  off the event loop this way.
- **Plain `requests`/`urllib3` sessions are rejected outright**, not just
  unauthenticated. `yfinance/data.py` raises `YFDataException` unless the
  session is specifically a `curl_cffi` session, since Yahoo's API blocks the
  TLS/HTTP fingerprint of a plain Python HTTP client, so yfinance switched to
  `curl_cffi` with Chrome impersonation (`impersonate="chrome"`) to get past
  that; still true across the 0.2.x -> 1.x line (re-verified against
  yfinance 1.5.2). A custom `requests.Session` subclass (the obvious way to
  inject a timeout) fails with `"Yahoo API requires curl_cffi session not
  <class ...>"`, found by
  actually running the import flow against a real ticker, not from any
  yfinance error message alone.

Any fetch failure here (timeout, this rejection, a genuine network error,
or a malformed Yahoo response) is caught and re-raised as `YFinanceFetchError`
(a `RuntimeError` subclass), which `balance_sheet_routes.py` maps to `502`,
kept distinct from the `ValueError`/`400` "no data for this ticker/year"
case (see the balance-sheets table in [API Reference](api.md)).

## Company hierarchy vs. the old `Vertical` model

The pre-migration repo (see git history prior to this migration) had an
unused `Vertical` model alongside `Company.parent_company_id`, which already
models the same hierarchy. Dropped in this migration: a vertical (e.g. Jio
Platforms under Reliance Industries) is just an ordinary child `Company` row.
