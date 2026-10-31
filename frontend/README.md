# Stockroom distributor frontend

Next.js app for distributor inventory, customers, and orders. It lives separately from the FastAPI backend in the repository root.

## Run locally

1. From the repository root, start the API with `python -m uvicorn main:app --reload`.
2. In `frontend/`, copy `.env.local.example` to `.env.local` if the API is not at `http://127.0.0.1:8000`.
3. In `frontend/`, run `npm install`, then `npm run dev`.
4. Open `http://localhost:3000` and sign in with a distributor account created through `/seller/register`.

The backend allows the local frontend origin by default. For another web origin, set backend `FRONTEND_ORIGINS` to a comma-separated list of allowed origins, then restart the API.

## Implemented screens

- Sign in using the seller login endpoint; the bearer token is kept in browser local storage.
- Overview with stock counts, customer count, open orders, inventory preview, and recent orders.
- Overview customer performance chart showing weekly cumulative sales for customers ranked in the top five during the selected analysis window; customer lines appear/disappear when the ranking changes.
- Inventory listing with all, running-low (1-9 units), and finished (0 units) filters, plus add/update form and per-product Edit actions for name, stock, and price. Edited names are specific to the distributor's inventory; the shared catalog name is preserved.
- Customer directory and customer creation.
- Orders grouped by customer; confirmed history is unpaged, while delivered and cancelled history uses five orders per page, newest first.
- Customer order creation, delivery status updates, and per-line price edits on a specific order.
- Select several confirmed orders for one customer, choose credit or due-on-receipt terms and optionally calculate 13% VAT, then save a numbered invoice and deliver them together.
- Invoice history with customer snapshots, printable bill copies, partial/full payment recording, balances, and an Excel workbook export with Invoices, Invoice Items, and Payments sheets.
- Analysis for invoiced product sales pace, average daily unit sales, stock-cover estimates, customer purchase rankings, purchase trends, balances due, and average payment time on fully paid invoices. Includes 30/90-day views, customer sorting, and the weekly running-sales line chart that dynamically shows customers ranked in the top five at each point.

Catalog and order prices are entered as whole NPR rupees; invoice VAT totals and payment entries retain two decimal places for paisa.

The VAT option is a basic 13% calculation for distributors who have confirmed their VAT registration and the tax treatment of the items. Seller tax registration/PAN details, due dates, and Department-approved e-invoice integration are not configured, so do not treat the generated document as confirmed statutory invoice compliance without accountant/IRD review. Apply migrations with `alembic upgrade head` before starting the updated app.

Analysis is based on invoices saved in Stockroom. Earlier delivered orders without invoices are excluded. Sales values exclude VAT; outstanding balances include VAT. Profitability is intentionally not shown because purchase/stock costs are not recorded yet.

## Notes

- Distributor account registration is not exposed in the UI. Use the backend endpoint to create accounts; this avoids presenting public signup as a confirmed product requirement.
- The UI calls the existing API directly. It needs the FastAPI service running and reachable from the browser.
