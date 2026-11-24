# System Flow & Service Overview

## What the Service Does

This service is an **asynchronous Flask API** for managing products, inventory reservations, currency-converted pricing, and sales reports. It separates responsibilities across four modules:

- **Entrypoint (`wsgi.py`)**: Creates a `ProcessPoolExecutor` (using `forkserver` for CPU-bound work), instantiates `RatesClient`, builds the Flask application via `create_app(...)`, and seeds a demo product (`widget`, `1000` cents in `EUR`, `5` units in stock) using a test client at startup.
- **HTTP & Async Routing (`app.py`)**: Defines async Flask route handlers for products, stock levels, multi-currency price lookups, stock reservations, and sales reporting.
- **Exchange Rates Client (`rates.py`)**: Wraps `httpx.AsyncClient` to fetch exchange rates from `/v2/rate/{base}/{quote}`, retries transient transport errors with `tenacity`, maps HTTP `422` to `UnknownCurrency`, and translates HTTP/network failures into `RatesUnavailable`.
- **Sales Reporting (`reports.py`)**: Generates synthetic order data (`load_orders`) and aggregates revenue and unit counts per SKU (`sales_report`) to return the top products.

---

## High-Level System Architecture

```text
                        +-------------------------+
                        |   Client / HTTP Caller  |
                        +------------+------------+
                                     |
                                     v
                        +-------------------------+
                        |  Flask App (app.py)     |
                        |  async def view routes  |
                        +----+-------+-------+----+
                             |       |       |
       +---------------------+       |       +---------------------+
       | (I/O: Exchange Rates)       | (In-Memory State)           | (CPU: Sales Report)
       v                             v                             v
+-----------------------+   +-----------------+       +---------------------------+
| RatesClient (rates.py)|   | products dict   |       | ProcessPoolExecutor       |
| httpx.AsyncClient     |   | stock dict +    |       | (forkserver in wsgi.py)   |
| + tenacity retries    |   | stock_lock      |       | -> reports.sales_report() |
+-----------+-----------+   +-----------------+       +---------------------------+
            |
            v
+-----------------------+
| Frankfurter Rates API  |
| /v2/rate/{base}/{quote}|
+-----------------------+