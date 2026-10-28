# Project context for any AI assistant

Last reviewed: 2026-10-28. This is a snapshot of the actual workspace, including uncommitted changes. Update it after meaningful changes; inspect current source before making edits.

## Keeping this file with the project

Keep `PROJECT_CONTEXT.md` in the project root alongside `main.py`, and include it in version control with the source. When sharing the project as a folder or ZIP, include this file. You can also attach it alone to an AI chat for orientation; exact implementation work may still require the relevant source files.

This is a living document. After adding or changing a feature, update the existing sections so they describe the current project, rather than only appending notes that contradict older information. Updates are manual or made by an AI with access to the project; this file does not automatically track code changes.

After each meaningful feature change:

1. Update the review date and current implementation summary.
2. Update affected file descriptions, endpoints, models, permissions, and business rules.
3. Remove resolved gaps and record any newly discovered limitations.
4. Record the test command and actual outcome; explicitly say if tests were not run. Never carry forward an old result as verification of new code.
5. Record confirmed product decisions, keeping proposed work separate from implemented features.
6. Add a short entry to the recent changes below. Keep the main sections authoritative and trim old entries when they stop being useful.

Reusable prompt after feature work:

> Update PROJECT_CONTEXT.md to match the current project after these changes: [describe the feature]. Inspect the affected source files, revise outdated sections, record confirmed decisions and remaining gaps, and add a dated recent-change entry. Record only tests actually run and their outcomes. Keep the distributor-first direction and exclude secrets. If you cannot edit the project directly, give me the complete updated Markdown file to replace the existing one.

## Recent changes

| Date | Change | Verification |
| --- | --- | --- |
| 2026-10-28 | Added inventory filters for low/finished stock, customer-grouped order histories, newest-first order display, five-order pages for delivered/cancelled histories, unpaged confirmed orders, and per-order line-item repricing. | Frontend `npm run lint` and `npm run build` passed; backend files passed `py_compile` and FastAPI OpenAPI generation. Backend pytest and endpoint smoke checks were not run for this change. |
| 2026-10-28 | Added a persistent light/dark theme toggle to the login and distributor workspace screens. Dark styles cover navigation, cards, forms, tables, alerts, and status labels. | `npm run lint` and `npm run build` passed. |
| 2026-10-28 | Fixed async frontend forms resetting `event.currentTarget` after awaiting API calls; handlers now retain the form element. Applied to inventory, customer, and order forms. | `npm run lint` and `npm run build` passed. Read-only check confirmed the product from the reported inventory submission was already stored in `business.db`; the error was raised during UI reset after the successful API response. |
| 2026-10-24 | Added the first separate Next.js distributor frontend in `frontend/` with sign-in, overview, inventory, customers, and order workflows; increased type sizes for readability. Added `GET /seller/me` for account bootstrap and configurable FastAPI CORS origins. | `npm run lint` and `npm run build` passed on Next.js 16.4.3; dependency install reported 0 vulnerabilities. API smoke flow passed for registration/login, inventory write/read, customer create/list, order create/detail/delivery, frontend HTTP 200, and persisted customer/order/stock after API restart using `order_utils/frontend-smoke.db`. Full backend pytest suite not run. |
| 2026-10-08 | Fixed SQLite migration table rebuilds with existing order items: foreign-key enforcement is temporarily disabled on the migration connection, integrity is checked before/after, and explicit transactions allow rollback. Downgrade now recreates removed cart tables. Added real migration regression tests. | 31 passed, 1 warning, using a temporary test database. |
| 2026-10-08 | Refreshed the handoff: distributor customer create/list/view/update is implemented; inventory writes enforce seller ownership; shared product names are preserved; customer records remain separate from order/login identities. | Current backend suite: 27 passed, 1 warning. |
| 2026-10-07 | Created the project handoff from the current source and added the ongoing update workflow. | Existing backend suite: 12 passed, 1 warning before these documentation-only updates. |

## Message from the project owner

I am building a distributor-focused business management application. The main purpose is to help distributors manage customers and everyday operations, including inventory, orders, and deliveries. It will also have simple customer features. Prioritize useful distributor workflows when discussing future work. The code currently uses the word `seller`; treat this as the existing implementation of the distributor side, without assuming that the full distributor management system already exists.

Help me continue from the current implementation. Explain changes clearly and distinguish implemented behavior from future ideas. Do not assume this is primarily a consumer shopping app or invent requirements I have not confirmed.

## Where we are now

The project contains a FastAPI backend and a separate Next.js distributor frontend in `frontend/`. The frontend has sign-in, overview, inventory, customer, and order screens. Inventory filters show all products, running-low stock (1-9 units), or finished stock (0 units). Orders are grouped by saved distributor customers or login accounts; confirmed histories are unpaged, while delivered and cancelled histories use five-order pages, all newest first by descending order ID. Sellers can change an item's price on a specific order without changing the inventory catalog price.

We are at the first distributor customer-management stage: sellers can create, list, view, and update customer records belonging to their inventory. Records include a required name and optional phone/address; customers do not need login accounts for these records. Inventory product updates are restricted to the inventory's seller.

The directory-to-order workflow is implemented: models and migration `46577a49b999` add nullable `directory_customer_id` referencing `customers`, make `customer_id` nullable, and require exactly one customer identity. Sellers can create an order for a customer directory record using `POST /seller/customers/{customer_id}/orders`, then list/view and deliver it. Customer-facing routes still use the authenticated user's ID as `customer_id`. Customer order history for directory customers, customer deletion, balances, and payments are not implemented. Migration verification used temporary databases and does not establish the current revision of the real business database.

The seller delivery endpoint and its permission/stock test are present. Customers cannot mark orders delivered. The existing test suite passes, but its coverage does not establish that every business rule or security boundary is complete.

## Technology and setup

- FastAPI, Pydantic v2-style schemas, SQLAlchemy ORM, SQLite by default.
- Password hashing uses `pwdlib.PasswordHash.recommended()`; tokens use PyJWT.
- `python-dotenv` loads the root `.env` in `order_utils/securities.py`.
- Application entry point: `main.py`, with FastAPI instance `app`.
- Local environment: `.venv`; tests use pytest and FastAPI TestClient.
- Alembic migrations are present in `migrations/`, configured by `alembic.ini`. The Next.js dependency manifest and lockfile are in `frontend/`; backend dependency manifest and deployment configuration are not present.

From the project root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# If uvicorn is installed:
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Configuration names, without secret values:

- `SECRET_KEY`: required by the token code.
- `ALGORITHM`: required by the token code.
- `DATABASE_URL`: optional override; defaults to `order_utils/business.db` using SQLite.

Do not include the real `.env`, credentials, tokens, or customer/database contents in shared context. This file contains no secret values.

## Source map

| File | Responsibility |
| --- | --- |
| `main.py` | Builds the app, configures CORS from `FRONTEND_ORIGINS` (defaults to `http://localhost:3000`), and includes public products, protected products, orders, auth, and seller routers. |
| `routes/auth.py` | Customer/user registration, login, and `get_current_user` bearer-token validation. |
| `routes/products.py` | Public inventory browsing, authenticated shared catalog reads, seller-owned inventory product upserts. |
| `routes/orders.py` | Customer-owned order creation, listing, details, item additions/removals, cancellation. |
| `routes/seller.py` | Seller registration/login/profile (`GET /seller/me`), inventory membership checks, customer-grouped order summaries/history pages/recent orders, seller order viewing/delivery/repricing, inventory-scoped customer CRUD, and offline customer order creation. |
| `frontend/` | Next.js 16 distributor app: login, dashboard, inventory stock filters/updates, customer directory, grouped order histories, pagination, order delivery/repricing. Setup notes are in `frontend/README.md`. |
| `order_utils/Business.py` | `Product`, `Inventory`, and lowercase `orders` business class; stock/order transactions and order line repricing. Routes alias `orders` as `BusinessOrder`. |
| `order_utils/models.py` | SQLAlchemy tables and constraints; import-time table creation has been removed. |
| `migrations/env.py` | Uses the application engine and metadata; SQLite migration transactions, temporary foreign-key enforcement changes, and integrity checks. |
| `migrations/versions/` | Baseline schema and offline-customer order schema migration; the latter removes legacy cart tables. |
| `order_utils/schemas.py` | Request validation and response models. |
| `order_utils/storage.py` | Engine, sessions, read/dependency contexts, SQLite write transactions and foreign-key pragma. |
| `order_utils/securities.py` | Password hashing, environment configuration, JWT creation. |
| `tests/conftest.py` | Sets DATABASE_URL, SECRET_KEY, and ALGORITHM before app import; verifies the temporary database path and resets tables per test. |
| `tests/helpers.py` | Customer and seller registration/login helpers. |
| `tests/test_fileislong.py` | Main customer/inventory/auth/seller API regression tests. |
| `tests/test_seller_customers.py` | Seller delivery permissions/status/stock plus customer management, isolation, authentication, and validation tests. |
| `tests/test_inventory_permissions.py` | Inventory ownership enforcement and protection against renaming shared products through inventory upserts. |
| `tests/test_offline_orders.py` | Distributor order creation for saved customers, order access isolation, stock deduction, delivery, and rejection behavior. |
| `pytest.ini` | Limits test discovery to `tests`. |
| `tests/test_migrations.py` | Real Alembic subprocess tests: existing order/item preservation, customer identity constraints, downgrade/re-upgrade, offline-order downgrade refusal, and broken-reference rejection. |
| `tests/__init__.py` | Empty package marker, needed for relative helper imports. |

`order_utils/main.py`, `order_utils/init.py`, and `order_utils/test.py` are empty. `order_utils/payment.py` is only a small tuple/print experiment, not payment functionality. The IDE mentioned `tests/init.py`, but that file was not present on disk during review; do not confuse it with `tests/__init__.py`.

## Current data model

- `products`: shared catalog, string `id`, `name`.
- `inventories`: integer `id`, `name`.
- `inventory_products`: composite key `(inventory_id, product_id)`, integer `stock` and `unit_price`, both nonnegative.
- `users`: integer `id`, unique `username`, `password_hash`. There is no explicit role column.
- `inventory_sellers`: inventory primary key and unique `user_id`, both foreign keys. Currently this permits one seller per inventory and one inventory per seller; it is not a multi-staff permission model.
- `customers`: integer `id`, indexed inventory foreign key, required `name`, nullable `phone` and `address`. These are inventory-owned contact records, separate from login users; distributor orders reference them through `directory_customer_id`.
- `orders`: integer `id`, nullable `customer_id` (login user ID, no users foreign key), nullable indexed `directory_customer_id` (customers foreign key), inventory foreign key, and status restricted to `confirmed`, `cancelled`, or `delivered`. A check requires exactly one of the two customer IDs to be set.
- `order_items`: composite key `(order_id, product_id)`, positive integer `quantity`, nonnegative integer `unit_price`; order and product foreign keys.

Prices and totals are integers. Currency and whether those integers represent major or minor monetary units have not been defined. Product identity/name is global; stock and current price belong to an inventory. Inventory upserts create missing catalog products but preserve the name of an existing product, even when a different name is submitted. Order items store their own unit price. Adding quantity to an existing item keeps its stored price.

## Current HTTP API

| Access | Method and path | Behavior |
| --- | --- | --- |
| Public | `POST /auth/register`, `POST /auth/login` | Register a user, obtain bearer token. |
| Public | `POST /seller/register`, `POST /seller/login` | Register user + inventory + seller mapping; seller login requires mapping. |
| Inventory seller | `GET /seller/me` | Return authenticated seller and associated inventory details for frontend bootstrap. |
| Public | `GET /inventories` | List inventories. |
| Public | `GET /inventories/{inventory_id}/products` | Inventory products including stock and price. |
| Public | `GET /inventories/{inventory_id}/products/{product_id}` | One inventory product. |
| Any authenticated user | `GET /products`, `GET /products/{product_id}` | Shared catalog reads. No `POST /products` route currently exists. |
| Inventory seller | `PUT /inventories/{inventory_id}/products` | Upsert products and set absolute stock/price; customers and other sellers receive 403. |
| Authenticated user | `POST /orders` | Create own order for an inventory. |
| Order customer | `GET /orders`, `GET /orders/{order_id}` | List own orders / view owned order. |
| Order customer | `POST /orders/{order_id}/items` | Add items to a confirmed order. |
| Order customer | `POST /orders/{order_id}/items/{product_id}/reject` | Remove requested quantity, up to quantity in the order. |
| Order customer | `POST /orders/{order_id}/cancel` | Cancel a confirmed order and restore stock. |
| Inventory seller | `GET /seller/orders`, `GET /seller/orders/{order_id}` | List/view orders for seller's inventory. |
| Inventory seller | `GET /seller/orders/recent` | Return the five latest orders for the overview. |
| Inventory seller | `GET /seller/order-customers` | List customers with orders, grouped by saved customer or login account with status counts/latest order ID. |
| Inventory seller | `GET /seller/order-customers/{customer_type}/{customer_id}/orders?status={confirmed\|delivered\|cancelled}&page=N` | View one customer's history newest first. Confirmed orders are unpaged; delivered/cancelled return at most five per page. |
| Inventory seller | `POST /seller/orders/{order_id}/deliver` | Mark a confirmed order delivered. |
| Inventory seller | `PATCH /seller/orders/{order_id}/items/{product_id}/price` | Change a line-item unit price on an order; recalculates its displayed subtotal and total without changing inventory stock/catalog price. |
| Inventory seller | `POST /seller/customers/{customer_id}/orders` | Create an inventory order for a customer-directory record; stock is deducted and rejected items are reported. |
| Inventory seller | `POST /seller/customers` | Create a customer in the seller's inventory; returns 201. |
| Inventory seller | `GET /seller/customers` | List own customer records, sorted by name then ID. |
| Inventory seller | `GET /seller/customers/{customer_id}` | View own customer; missing or another seller's customer returns 404. |
| Inventory seller | `PATCH /seller/customers/{customer_id}` | Update supplied contact fields only; missing or another seller's customer returns 404. |

FastAPI CORS permits `http://localhost:3000` by default. Set backend `FRONTEND_ORIGINS` to comma-separated allowed web origins in other environments.

There is no `POST /orders/{order_id}/deliver` customer endpoint. Seller accounts are ordinary users with an inventory mapping; customer-facing authenticated routes do not explicitly exclude sellers.

Customer inputs strip surrounding whitespace. Name length is 1–100, phone 1–30 when supplied, and address 1–300 when supplied. PATCH rejects an empty update, null name, and unknown fields with 422; phone/address can be cleared with null. Ownership is derived from the authenticated seller, not from a submitted inventory ID.

Example order request:

```json
{"inventory_id": 1, "items": [{"product_id": "test-product", "quantity": 4}]}
```

Example confirmation response:

```json
{"order_id": 1, "rejected": []}
```

Use `Authorization: Bearer <access_token>` on protected requests. Tokens contain user ID in `sub` and expire after five days. Token validation checks signature, expiry, required claims, and that the user still exists.

## Business behavior to preserve

1. Confirmation immediately deducts accepted quantities from available stock. There is no separate draft/cart or distributor approval state.
2. Confirmation can accept some requested items and reject others. It returns rejection details. A new order with no accepted items returns HTTP 409 without creating an order.
3. Adding items deducts more stock and merges quantities for an existing order product. Only confirmed orders are open for modification.
4. Partial item removal restores the actual removed stock. Removing every item changes status to cancelled; removed item rows are deleted.
5. Full cancellation restores stock once and retains remaining item rows as history. Repeat cancellation returns 409.
6. Delivery changes confirmed to delivered without deducting stock again. Repeat delivery returns 409.
7. Seller line-item repricing is scoped to an order owned by the seller's inventory. Repricing does not change inventory catalog prices or stock.
8. Customer order operations check the order's customer ID. Seller order operations check the seller's inventory. A different customer/seller must not gain access.
9. Write contexts use `BEGIN IMMEDIATE`, and confirmation uses a conditional stock update to avoid accepting quantities beyond available stock. This implementation is SQLite-specific; concurrency under load has not been validated by the current suite.

## Verified tests and limitations

Reviewed test command: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .test-tmp-migration-fix`.

Result on 2026-10-08 after the migration fix: **31 passed, 1 warning**. The warning is a Starlette deprecation warning about TestClient's use of `httpx`. Four tests exercise actual migrations; API fixtures still create their schema with `create_all`.

The recorded 2026-10-08 suite covered invalid/missing order tokens, customer order isolation, cancellation stock restoration, public inventory browsing, wrong-password rejection, adding/removing quantities, seller registration/login, seller order isolation, seller delivery permissions/status/stock, inventory mutation permissions, shared product name preservation, seller customer create/list/view/update, and offline customer order behaviors. On 2026-10-28, frontend lint/build and backend Python syntax checks passed for customer order browsing, inventory filters, and repricing. Backend pytest and API smoke checks were not run for that change.

The current run succeeded in the sandbox using an explicit workspace temporary directory and disabling the pytest cache. The previous review encountered temporary-directory permissions; this run did not require escalation.

The previous test configuration mismatch is resolved: `tests/conftest.py` now sets `SECRET_KEY` and `ALGORITHM` before importing the app, matching the application configuration names. It also verifies that the engine points at its temporary test database before any table reset.

## Known gaps and next-work candidates

These are observations and recommendations, not already approved feature requirements:

1. Add regression coverage for `/seller/me`, CORS, customer-grouped histories/pagination, and confirmed-order repricing.
2. Order recency currently uses descending integer order IDs because the schema has no timestamps. Add timestamps if calendar dates or exact creation times are needed.
3. Define delivery details and whether balances/credit/payment tracking are needed before adding those workflows.
4. Add a reproducible backend dependency manifest. Verify the actual database's revision/schema before applying migrations. The baseline creates tables for an empty database; adopting a pre-existing schema requires checking that it matches before stamping the baseline. SQLite batch migrations require a live connection; generating the full upgrade with `--sql` is not implemented.
5. Define money units and currency. The frontend currently labels values as integer `units` because the backend has not defined currency/scale.
6. Consider customer search, broader pagination, referential integrity, and role/staff access as product needs become clear.

Other absent capabilities include structured delivery addresses, invoices, payment processing, returns, reports, pagination/search, delivery scheduling, and staff roles. Customer records already have a free-text address field. Do not assume all absent capabilities are required just because they are listed here.

## Working-state notes for the next AI

The workspace contains uncommitted backend and frontend work. Inspect `git status` before making further changes and preserve the owner's work; this handoff is based on files on disk, not only committed code. Seller routes are included by the current `main.py`.

Read the relevant route, schema, model, and business method together before changing a workflow. Preserve stock restoration, delivery behavior, and access checks. Run tests against a temporary test database, never reset the real business database. Keep this context updated with implemented changes, actual test outcomes, and decisions the owner confirms.

Suggested opening prompt when sharing this file:

> Read the attached PROJECT_CONTEXT.md as the current project handoff. Our priority is distributor operations and customer management, with simple customer features. Distinguish existing code from planned features, and help me continue from this state. My next task is: [describe the task]. If you need exact code to implement it, tell me which files you need.
