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
- Inventory listing with all, running-low (1-9 units), and finished (0 units) filters, plus add/update form.
- Customer directory and customer creation.
- Orders grouped by customer; confirmed history is unpaged, while delivered and cancelled history uses five orders per page, newest first.
- Customer order creation, delivery status updates, and per-line price edits on a specific order.

The backend stores prices as integers but has no configured currency or major/minor unit. The UI labels displayed amounts as integer `units` so it does not assume a currency scale.

## Notes

- Distributor account registration is not exposed in the UI. Use the backend endpoint to create accounts; this avoids presenting public signup as a confirmed product requirement.
- The UI calls the existing API directly. It needs the FastAPI service running and reachable from the browser.
