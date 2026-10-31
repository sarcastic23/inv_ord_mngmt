from typing import Literal
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, case, func, select, update

from order_utils.models import (
    UserRow,
    InventoryRow,
    InventorySellerRow,
    CustomerRow,
    OrderRow,
    OrderItemRow,
    ProductRow,
    InventoryProductRow,
    InvoiceRow,
    InvoiceItemRow,
    PaymentRow,
)

from order_utils.schemas import (
    SellerCreate,
    SellerResponse,
    UserLogin,
    TokenResponse,
    UserResponse,
    OrderDeliveryResponse,
    CustomerResponse,
    CustomerCreate,
    CustomerUpdate,
    OrderSummaryResponse,
    OrderResponse,
    OrderConfirmationResponse,
    OrderItemsAdd,
    OrderItemPriceUpdate,
    CustomerOrderGroupResponse,
    CustomerOrderHistoryResponse,
    BulkOrderDeliveryRequest,
    BulkOrderDeliveryResponse,
    InvoiceResponse,
    PaymentCreate,
    
)
from order_utils.securities import (
    hash_password,
    verify_password,
    create_access_token,
)
from order_utils.storage import get_db, get_db_write
from .auth import get_current_user

from order_utils.Business import Inventory, orders as BusinessOrder


router = APIRouter(prefix="/seller", tags=["Seller"])

DUMMY_HASH = hash_password("unused-dummy-password")



def get_seller_inventory(
    user: UserResponse = Depends(get_current_user)
) -> int:
    with get_db() as db:
        inventory_id = db.scalar(
            select(InventorySellerRow.inventory_id)
            .where(InventorySellerRow.user_id == user.id)
        )

        if inventory_id is None:
            raise HTTPException(
                status_code=403,
                detail="Seller access required"
            )

        return inventory_id


def _issue_invoice(db, inventory_id: int, orders: list[OrderRow], vat_rate_bps: int = 0, payment_terms: str = "credit") -> InvoiceRow:
    first = orders[0]
    if first.directory_customer_id is not None:
        customer = db.get(CustomerRow, first.directory_customer_id)
        customer_name = customer.name if customer else "Customer"
        phone = customer.phone if customer else None
        address = customer.address if customer else None
    else:
        customer = db.get(UserRow, first.customer_id)
        customer_name = customer.username if customer else "Customer"
        phone = address = None
    inventory = db.get(InventoryRow, inventory_id)
    subtotal = 0
    vat_total = Decimal("0.00")
    invoice = InvoiceRow(
        invoice_number="PENDING", inventory_id=inventory_id,
        customer_name=customer_name, customer_phone=phone,
        customer_address=address, seller_name=inventory.name,
        payment_terms=payment_terms,
        is_vat_invoice=vat_rate_bps > 0, vat_rate_bps=vat_rate_bps,
        subtotal=0, vat_total=Decimal("0.00"), total=Decimal("0.00"),
        issued_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    db.add(invoice)
    db.flush()
    invoice.invoice_number = f"INV-{inventory_id}-{invoice.id:06d}"
    for order in orders:
        items = db.execute(
            select(OrderItemRow, func.coalesce(InventoryProductRow.name_override, ProductRow.name))
            .join(ProductRow, ProductRow.id == OrderItemRow.product_id)
            .outerjoin(
                InventoryProductRow,
                and_(
                    InventoryProductRow.inventory_id == inventory_id,
                    InventoryProductRow.product_id == OrderItemRow.product_id,
                ),
            )
            .where(OrderItemRow.order_id == order.id)
        ).all()
        for item, product_name in items:
            line_subtotal = item.quantity * item.unit_price
            tax = (Decimal(line_subtotal * vat_rate_bps) / Decimal(10000)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line_subtotal
            vat_total += tax
            db.add(InvoiceItemRow(
                invoice_id=invoice.id, product_id=item.product_id,
                product_name=product_name, quantity=item.quantity,
                unit_price=item.unit_price, subtotal=line_subtotal,
                vat_rate_bps=vat_rate_bps, vat_amount=tax,
                total=line_subtotal + tax,
            ))
        order.invoice_id = invoice.id
    invoice.subtotal = subtotal
    invoice.vat_total = vat_total
    invoice.total = Decimal(subtotal) + vat_total
    return invoice


def _invoice_payload(db, invoice: InvoiceRow) -> dict:
    items = db.scalars(select(InvoiceItemRow).where(InvoiceItemRow.invoice_id == invoice.id).order_by(InvoiceItemRow.id)).all()
    payments = db.scalars(select(PaymentRow).where(PaymentRow.invoice_id == invoice.id)).all()
    paid = sum((payment.amount for payment in payments), Decimal("0.00"))
    return {
        "id": invoice.id, "invoice_number": invoice.invoice_number,
        "customer_name": invoice.customer_name, "customer_phone": invoice.customer_phone,
        "customer_address": invoice.customer_address, "seller_name": invoice.seller_name,
        "payment_terms": invoice.payment_terms,
        "issued_at": invoice.issued_at, "is_vat_invoice": invoice.is_vat_invoice,
        "vat_rate_bps": invoice.vat_rate_bps, "subtotal": invoice.subtotal,
        "vat_total": invoice.vat_total, "total": invoice.total,
        "amount_paid": paid, "balance": max(Decimal("0.00"), invoice.total - paid),
        "payment_status": "paid" if paid >= invoice.total else "partially_paid" if paid else "unpaid",
        "items": [{"product_id": item.product_id, "product_name": item.product_name,
                   "quantity": item.quantity, "unit_price": item.unit_price,
                   "subtotal": item.subtotal, "vat_rate_bps": item.vat_rate_bps,
                   "vat_amount": item.vat_amount, "total": item.total} for item in items],
    }


@router.get("/me", response_model=SellerResponse)
def get_seller_profile(user: UserResponse = Depends(get_current_user)):
    with get_db() as db:
        mapping = db.scalar(
            select(InventorySellerRow)
            .where(InventorySellerRow.user_id == user.id)
        )
        if mapping is None:
            raise HTTPException(status_code=403, detail="Seller access required")
        inventory = db.get(InventoryRow, mapping.inventory_id)
        return SellerResponse(
            id=user.id,
            username=user.username,
            inventory_id=inventory.id,
            inventory_name=inventory.name,
        )


def load_seller_order(
    order_id: int,
    inventory_id: int = Depends(get_seller_inventory)
) -> BusinessOrder:
    with get_db() as db:
        row = db.get(OrderRow, order_id)

        if row is None:
            raise HTTPException(status_code=404, detail="Order not found")

        if row.inventory_id != inventory_id:
            raise HTTPException(
                status_code=403,
                detail="Order belongs to another seller"
            )

        customer_id = row.customer_id
        directory_customer_id = row.directory_customer_id

    try:
        return BusinessOrder(
            inventory=Inventory(inventory_id),
            customer_id=customer_id,
            directory_customer_id=directory_customer_id,
            order_id=order_id
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))


def serialize_seller_orders(rows: list[OrderRow]) -> list[dict]:
    if not rows:
        return []

    order_ids = [row.id for row in rows]
    with get_db() as db:
        items = db.execute(
            select(
                OrderItemRow.order_id,
                OrderItemRow.product_id,
                func.coalesce(InventoryProductRow.name_override, ProductRow.name),
                OrderItemRow.quantity,
                OrderItemRow.unit_price,
            )
            .join(ProductRow, ProductRow.id == OrderItemRow.product_id)
            .join(OrderRow, OrderRow.id == OrderItemRow.order_id)
            .outerjoin(
                InventoryProductRow,
                and_(
                    InventoryProductRow.inventory_id == OrderRow.inventory_id,
                    InventoryProductRow.product_id == OrderItemRow.product_id,
                ),
            )
            .where(OrderItemRow.order_id.in_(order_ids))
            .order_by(OrderItemRow.order_id, func.coalesce(InventoryProductRow.name_override, ProductRow.name))
        ).all()

    items_by_order: dict[int, list[dict]] = {}
    for order_id, product_id, name, quantity, unit_price in items:
        subtotal = quantity * unit_price
        items_by_order.setdefault(order_id, []).append({
            "product_id": product_id,
            "name": name,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

    return [
        {
            "order_id": row.id,
            "customer_id": row.customer_id,
            "directory_customer_id": row.directory_customer_id,
            "inventory_id": row.inventory_id,
            "status": row.status,
            "items": items_by_order.get(row.id, []),
            "total": sum(item["subtotal"] for item in items_by_order.get(row.id, [])),
        }
        for row in rows
    ]




@router.get("/orders", response_model=list[OrderSummaryResponse])
def list_seller_orders(
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        rows = db.scalars(
            select(OrderRow)
            .where(OrderRow.inventory_id == inventory_id)
            .order_by(OrderRow.id.desc())
        ).all()

        return [
            {
                "order_id": row.id,
                "inventory_id": row.inventory_id,
                "status": row.status
            }
            for row in rows
        ]



@router.get("/orders/recent", response_model=list[OrderResponse])
def list_recent_seller_orders(
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        rows = db.scalars(
            select(OrderRow)
            .where(OrderRow.inventory_id == inventory_id)
            .order_by(OrderRow.id.desc())
            .limit(5)
        ).all()

    return serialize_seller_orders(rows)


@router.get("/order-customers", response_model=list[CustomerOrderGroupResponse])
def list_seller_order_customers(
    inventory_id: int = Depends(get_seller_inventory)
):
    confirmed_count = func.sum(
        case((OrderRow.status == "confirmed", 1), else_=0)
    )
    delivered_count = func.sum(
        case((OrderRow.status == "delivered", 1), else_=0)
    )
    cancelled_count = func.sum(
        case((OrderRow.status == "cancelled", 1), else_=0)
    )

    with get_db() as db:
        directory_rows = db.execute(
            select(
                CustomerRow.id,
                CustomerRow.name,
                CustomerRow.phone,
                CustomerRow.address,
                func.count(OrderRow.id),
                confirmed_count,
                delivered_count,
                cancelled_count,
                func.max(OrderRow.id),
            )
            .join(
                OrderRow,
                OrderRow.directory_customer_id == CustomerRow.id,
            )
            .where(
                CustomerRow.inventory_id == inventory_id,
                OrderRow.inventory_id == inventory_id,
            )
            .group_by(
                CustomerRow.id,
                CustomerRow.name,
                CustomerRow.phone,
                CustomerRow.address,
            )
        ).all()

        account_rows = db.execute(
            select(
                UserRow.id,
                UserRow.username,
                func.count(OrderRow.id),
                confirmed_count,
                delivered_count,
                cancelled_count,
                func.max(OrderRow.id),
            )
            .join(OrderRow, OrderRow.customer_id == UserRow.id)
            .where(OrderRow.inventory_id == inventory_id)
            .group_by(UserRow.id, UserRow.username)
        ).all()

    groups = [
        CustomerOrderGroupResponse(
            customer_type="directory",
            customer_id=row[0],
            customer_name=row[1],
            phone=row[2],
            address=row[3],
            total_orders=row[4],
            confirmed_orders=row[5] or 0,
            delivered_orders=row[6] or 0,
            cancelled_orders=row[7] or 0,
            latest_order_id=row[8],
        )
        for row in directory_rows
    ]
    groups.extend(
        CustomerOrderGroupResponse(
            customer_type="account",
            customer_id=row[0],
            customer_name=row[1],
            total_orders=row[2],
            confirmed_orders=row[3] or 0,
            delivered_orders=row[4] or 0,
            cancelled_orders=row[5] or 0,
            latest_order_id=row[6],
        )
        for row in account_rows
    )
    return sorted(groups, key=lambda group: group.latest_order_id, reverse=True)


@router.get(
    "/order-customers/{customer_type}/{customer_id}/orders",
    response_model=CustomerOrderHistoryResponse,
)
def list_customer_order_history(
    customer_type: Literal["directory", "account"],
    customer_id: int,
    status: Literal["confirmed", "delivered", "cancelled"] = "confirmed",
    page: int = Query(default=1, ge=1),
    inventory_id: int = Depends(get_seller_inventory),
):
    groups = list_seller_order_customers(inventory_id)
    customer = next(
        (
            group for group in groups
            if group.customer_type == customer_type
            and group.customer_id == customer_id
        ),
        None,
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_column = (
        OrderRow.directory_customer_id
        if customer_type == "directory"
        else OrderRow.customer_id
    )
    filters = (
        OrderRow.inventory_id == inventory_id,
        customer_column == customer_id,
        OrderRow.status == status,
    )
    with get_db() as db:
        total = db.scalar(
            select(func.count(OrderRow.id)).where(*filters)
        ) or 0
        query = (
            select(OrderRow)
            .where(*filters)
            .order_by(OrderRow.id.desc())
        )
        if status == "confirmed":
            page_size = max(total, 1)
        else:
            page_size = 5
            query = query.offset((page - 1) * page_size).limit(page_size)
        rows = db.scalars(query).all()

    order_details = serialize_seller_orders(rows)

    return CustomerOrderHistoryResponse(
        customer=customer,
        status=status,
        page=page if status != "confirmed" else 1,
        page_size=page_size,
        total=total,
        page_count=max(1, (total + page_size - 1) // page_size),
        orders=order_details,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
def view_seller_order(
    order: BusinessOrder = Depends(load_seller_order)
):   #we should just use route's order_id to pass it to load_seller_order,,but rn im bored ,, idnt hv energy to update these schemas ...
    result = order.view_order()

    if result is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return result


@router.post(
    "/orders/{order_id}/deliver",
    response_model=OrderDeliveryResponse
)
def deliver_seller_order(
    order_id: int,
    inventory_id: int = Depends(get_seller_inventory),
):
    with get_db_write() as db:
        order = db.get(OrderRow, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.inventory_id != inventory_id:
            raise HTTPException(status_code=403, detail="Order belongs to another seller")
        if order.status != "confirmed" or order.invoice_id is not None:
            raise HTTPException(status_code=409, detail="Only uninvoiced confirmed orders can be delivered")
        invoice = _issue_invoice(db, inventory_id, [order])
        order.status = "delivered"
        result = {"order_id": order.id, "status": "delivered", "invoice_id": invoice.id, "invoice_number": invoice.invoice_number}
    return result


@router.post(
    "/orders/deliver-batch",
    response_model=BulkOrderDeliveryResponse,
)
def deliver_seller_orders(
    data: BulkOrderDeliveryRequest,
    inventory_id: int = Depends(get_seller_inventory),
):
    if len(set(data.order_ids)) != len(data.order_ids):
        raise HTTPException(status_code=422, detail="Order IDs must be unique")

    with get_db_write() as db:
        rows = db.scalars(
            select(OrderRow).where(OrderRow.id.in_(data.order_ids))
        ).all()
        rows_by_id = {row.id: row for row in rows}

        if len(rows_by_id) != len(data.order_ids):
            raise HTTPException(status_code=404, detail="One or more orders were not found")
        if any(row.inventory_id != inventory_id for row in rows):
            raise HTTPException(status_code=403, detail="An order belongs to another seller")

        customer_identities = {
            (row.customer_id, row.directory_customer_id)
            for row in rows
        }
        if len(customer_identities) != 1:
            raise HTTPException(
                status_code=409,
                detail="All orders in a bill must belong to the same customer",
            )
        if any(row.status != "confirmed" or row.invoice_id is not None for row in rows):
            raise HTTPException(
                status_code=409,
                detail="Only confirmed orders can be delivered together",
            )

        invoice = _issue_invoice(db, inventory_id, [rows_by_id[order_id] for order_id in data.order_ids], data.vat_rate_bps, data.payment_terms)
        result = db.execute(
            update(OrderRow)
            .where(
                OrderRow.id.in_(data.order_ids),
                OrderRow.inventory_id == inventory_id,
                OrderRow.status == "confirmed",
            )
            .values(status="delivered", invoice_id=invoice.id)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != len(data.order_ids):
            raise HTTPException(
                status_code=409,
                detail="Orders changed while the bill was being delivered",
            )

        invoice_id = invoice.id
        invoice_number = invoice.invoice_number
    return {"order_ids": data.order_ids, "status": "delivered", "invoice_id": invoice_id, "invoice_number": invoice_number}


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_seller_invoices(inventory_id: int = Depends(get_seller_inventory)):
    with get_db() as db:
        invoices = db.scalars(select(InvoiceRow).where(InvoiceRow.inventory_id == inventory_id).order_by(InvoiceRow.id.desc())).all()
        return [_invoice_payload(db, invoice) for invoice in invoices]


def _analysis_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


@router.get("/analysis")
def get_seller_analysis(
    days: Literal[30, 90] = Query(default=30),
    inventory_id: int = Depends(get_seller_inventory),
):
    """Summarize invoiced sales only; this deliberately does not estimate profit."""
    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)
    customer_bucket_days = 7
    customer_bucket_count = (days + customer_bucket_days - 1) // customer_bucket_days
    customer_bucket_labels = [
        (current_start + timedelta(days=index * customer_bucket_days)).date().isoformat()
        for index in range(customer_bucket_count)
    ]
    with get_db() as db:
        invoices = db.scalars(
            select(InvoiceRow)
            .where(InvoiceRow.inventory_id == inventory_id)
            .order_by(InvoiceRow.issued_at)
        ).all()
        invoice_ids = [invoice.id for invoice in invoices]
        items = db.scalars(
            select(InvoiceItemRow)
            .where(InvoiceItemRow.invoice_id.in_(invoice_ids))
            .order_by(InvoiceItemRow.id)
        ).all() if invoice_ids else []
        payments = db.scalars(
            select(PaymentRow)
            .where(PaymentRow.invoice_id.in_(invoice_ids))
            .order_by(PaymentRow.paid_at, PaymentRow.id)
        ).all() if invoice_ids else []
        order_identities = db.execute(
            select(OrderRow.invoice_id, OrderRow.customer_id, OrderRow.directory_customer_id)
            .where(OrderRow.invoice_id.in_(invoice_ids))
        ).all() if invoice_ids else []
        stock_rows = db.execute(
            select(InventoryProductRow.product_id, func.coalesce(InventoryProductRow.name_override, ProductRow.name), InventoryProductRow.stock)
            .join(ProductRow, ProductRow.id == InventoryProductRow.product_id)
            .where(InventoryProductRow.inventory_id == inventory_id)
        ).all()

    invoice_by_id = {invoice.id: invoice for invoice in invoices}
    items_by_invoice: dict[int, list[InvoiceItemRow]] = {}
    for item in items:
        items_by_invoice.setdefault(item.invoice_id, []).append(item)
    identities_by_invoice: dict[int, set[tuple[str, int]]] = {}
    for invoice_id, account_id, directory_id in order_identities:
        if invoice_id is None:
            continue
        identity = ("directory", directory_id) if directory_id is not None else ("account", account_id)
        identities_by_invoice.setdefault(invoice_id, set()).add(identity)

    payments_by_invoice: dict[int, list[PaymentRow]] = {}
    paid_by_invoice: dict[int, Decimal] = {}
    payment_received_in_period = Decimal("0.00")
    for payment in payments:
        payments_by_invoice.setdefault(payment.invoice_id, []).append(payment)
        paid_by_invoice[payment.invoice_id] = paid_by_invoice.get(payment.invoice_id, Decimal("0.00")) + payment.amount
        if _analysis_datetime(payment.paid_at) >= current_start:
            payment_received_in_period += payment.amount

    product_metrics: dict[str, dict] = {}
    for product_id, product_name, stock in stock_rows:
        product_metrics[product_id] = {
            "product_id": product_id, "product_name": product_name, "stock": stock,
            "units_sold": 0, "units_previous_period": 0,
            "sales_value": 0, "last_sold_at": None,
        }
    customer_metrics: dict[tuple[str, int] | tuple[str, str], dict] = {}
    summary_sales = 0
    summary_units = 0
    period_invoice_count = 0
    total_outstanding = Decimal("0.00")

    for invoice in invoices:
        issued = _analysis_datetime(invoice.issued_at)
        paid = paid_by_invoice.get(invoice.id, Decimal("0.00"))
        total_outstanding += max(Decimal("0.00"), invoice.total - paid)
        in_current = current_start <= issued <= now
        in_previous = previous_start <= issued < current_start
        invoice_items = items_by_invoice.get(invoice.id, [])
        item_subtotal = sum(item.subtotal for item in invoice_items)
        item_units = sum(item.quantity for item in invoice_items)
        if in_current:
            summary_sales += item_subtotal
            summary_units += item_units
            period_invoice_count += 1

        identities = identities_by_invoice.get(invoice.id) or {("invoice", str(invoice.id))}
        for identity in identities:
            customer = customer_metrics.setdefault(identity, {
                "customer_key": f"{identity[0]}:{identity[1]}",
                "customer_name": invoice.customer_name,
                "invoice_count": 0, "sales_value": 0, "units_purchased": 0,
                "sales_current_period": 0, "sales_previous_period": 0,
                "period_invoice_count": 0, "outstanding_balance": Decimal("0.00"),
                "last_purchase_at": None, "settlement_days": [],
                "sales_by_bucket": [0 for _ in customer_bucket_labels],
            })
            customer["invoice_count"] += 1
            customer["sales_value"] += item_subtotal
            customer["units_purchased"] += item_units
            customer["outstanding_balance"] += max(Decimal("0.00"), invoice.total - paid)
            if customer["last_purchase_at"] is None or issued > customer["last_purchase_at"]:
                customer["last_purchase_at"] = issued
            if in_current:
                customer["sales_current_period"] += item_subtotal
                customer["period_invoice_count"] += 1
                bucket_index = min(
                    int((issued - current_start).total_seconds() // (customer_bucket_days * 86400)),
                    customer_bucket_count - 1,
                )
                customer["sales_by_bucket"][bucket_index] += item_subtotal
            elif in_previous:
                customer["sales_previous_period"] += item_subtotal

            if invoice.total > 0 and paid >= invoice.total:
                cumulative = Decimal("0.00")
                for payment in payments_by_invoice.get(invoice.id, []):
                    cumulative += payment.amount
                    if cumulative >= invoice.total:
                        paid_at = _analysis_datetime(payment.paid_at)
                        customer["settlement_days"].append(max(0.0, (paid_at - issued).total_seconds() / 86400))
                        break

        for item in invoice_items:
            metric = product_metrics.setdefault(item.product_id, {
                "product_id": item.product_id, "product_name": item.product_name,
                "stock": 0, "units_sold": 0, "units_previous_period": 0,
                "sales_value": 0, "last_sold_at": None,
            })
            if in_current:
                metric["units_sold"] += item.quantity
                metric["sales_value"] += item.subtotal
            elif in_previous:
                metric["units_previous_period"] += item.quantity
            if metric["last_sold_at"] is None or issued > metric["last_sold_at"]:
                metric["last_sold_at"] = issued

    products = []
    for metric in product_metrics.values():
        daily_rate = metric["units_sold"] / days
        previous_units = metric["units_previous_period"]
        metric["units_per_day"] = round(daily_rate, 2)
        metric["stock_days_remaining"] = round(metric["stock"] / daily_rate, 1) if daily_rate else None
        metric["change_percent"] = round((metric["units_sold"] - previous_units) / previous_units * 100, 1) if previous_units else None
        metric["last_sold_at"] = metric["last_sold_at"].isoformat() if metric["last_sold_at"] else None
        products.append(metric)
    products.sort(key=lambda row: (-row["units_sold"], row["product_name"].casefold()))

    customers = []
    customer_trend_rows = []
    for metric in customer_metrics.values():
        settlements = metric.pop("settlement_days")
        sales_by_bucket = metric.pop("sales_by_bucket")
        customer_trend_rows.append({
            "customer_key": metric["customer_key"],
            "customer_name": metric["customer_name"],
            "sales_by_bucket": sales_by_bucket,
        })
        metric["average_days_to_pay"] = round(sum(settlements) / len(settlements), 1) if settlements else None
        metric["settled_invoice_count"] = len(settlements)
        previous_sales = metric["sales_previous_period"]
        metric["change_percent"] = round((metric["sales_current_period"] - previous_sales) / previous_sales * 100, 1) if previous_sales else None
        metric["last_purchase_at"] = metric["last_purchase_at"].isoformat() if metric["last_purchase_at"] else None
        customers.append(metric)
    customers.sort(key=lambda row: (-row["sales_value"], row["customer_name"].casefold()))

    return {
        "days": days,
        "as_of": now.isoformat(timespec="seconds"),
        "coverage": "invoices_recorded_in_this_app",
        "summary": {
            "sales_value": summary_sales,
            "units_sold": summary_units,
            "invoice_count": period_invoice_count,
            "outstanding_balance": total_outstanding,
            "payments_received": payment_received_in_period,
        },
        "products": products,
        "customers": customers,
        "customer_trends": {
            "bucket_days": customer_bucket_days,
            "labels": customer_bucket_labels,
            "customers": customer_trend_rows,
        },
    }


@router.post("/invoices/{invoice_id}/payments", response_model=InvoiceResponse, status_code=201)
def add_invoice_payment(invoice_id: int, data: PaymentCreate, inventory_id: int = Depends(get_seller_inventory)):
    with get_db_write() as db:
        invoice = db.scalar(select(InvoiceRow).where(InvoiceRow.id == invoice_id, InvoiceRow.inventory_id == inventory_id))
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        current = db.scalar(select(func.coalesce(func.sum(PaymentRow.amount), 0)).where(PaymentRow.invoice_id == invoice.id)) or 0
        if data.amount > invoice.total - current:
            raise HTTPException(status_code=409, detail="Payment exceeds the outstanding balance")
        db.add(PaymentRow(invoice_id=invoice.id, amount=data.amount,
                          paid_at=data.paid_at.isoformat(timespec="seconds") if data.paid_at else datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          method=data.method, reference=data.reference))
        db.flush()
        payload = _invoice_payload(db, invoice)
    return payload


def _sheet_xml(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_num, row in enumerate(rows, 1):
        cells = []
        for col_num, value in enumerate(row, 1):
            col = ""
            n = col_num
            while n:
                n, rem = divmod(n - 1, 26)
                col = chr(65 + rem) + col
            ref = f"{col}{row_num}"
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{float(value) if isinstance(value, Decimal) else value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value if value is not None else ""))}</t></is></c>')
        xml_rows.append(f'<row r="{row_num}">{"".join(cells)}</row>')
    n = max((len(row) for row in rows), default=1)
    last_col = ""
    while n:
        n, rem = divmod(n - 1, 26)
        last_col = chr(65 + rem) + last_col
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>' + "".join(xml_rows) + f'</sheetData><autoFilter ref="A1:{last_col}{max(1, len(rows))}"/></worksheet>'


@router.get("/invoices/export")
def export_seller_invoices(inventory_id: int = Depends(get_seller_inventory)):
    with get_db() as db:
        invoices = db.scalars(select(InvoiceRow).where(InvoiceRow.inventory_id == inventory_id).order_by(InvoiceRow.id)).all()
        invoice_rows = [["Invoice", "Customer", "Phone", "Address", "Issued at", "VAT invoice", "Payment terms", "Subtotal (NPR)", "VAT (NPR)", "Total (NPR)", "Paid (NPR)", "Balance (NPR)", "Payment status"]]
        item_rows = [["Invoice", "Customer", "Product ID", "Product", "Quantity", "Unit price (NPR)", "Subtotal (NPR)", "VAT rate %", "VAT (NPR)", "Total (NPR)"]]
        payment_rows = [["Invoice", "Customer", "Paid at", "Amount (NPR)", "Method", "Reference"]]
        for invoice in invoices:
            payload = _invoice_payload(db, invoice)
            invoice_rows.append([invoice.invoice_number, invoice.customer_name, invoice.customer_phone or "", invoice.customer_address or "", invoice.issued_at, "Yes" if invoice.is_vat_invoice else "No", invoice.payment_terms, invoice.subtotal, invoice.vat_total, invoice.total, payload["amount_paid"], payload["balance"], payload["payment_status"]])
            for item in payload["items"]:
                item_rows.append([invoice.invoice_number, invoice.customer_name, item["product_id"], item["product_name"], item["quantity"], item["unit_price"], item["subtotal"], item["vat_rate_bps"] / 100, item["vat_amount"], item["total"]])
            for payment in db.scalars(select(PaymentRow).where(PaymentRow.invoice_id == invoice.id).order_by(PaymentRow.id)):
                payment_rows.append([invoice.invoice_number, invoice.customer_name, payment.paid_at, payment.amount, payment.method or "", payment.reference or ""])
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        workbook.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        workbook.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Invoices" sheetId="1" r:id="rId1"/><sheet name="Invoice Items" sheetId="2" r:id="rId2"/><sheet name="Payments" sheetId="3" r:id="rId3"/></sheets></workbook>')
        workbook.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/></Relationships>')
        for index, rows in enumerate((invoice_rows, item_rows, payment_rows), 1):
            workbook.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=distributor-transactions.xlsx"})


@router.patch(
    "/orders/{order_id}/items/{product_id}/price",
    response_model=OrderResponse,
)
def update_seller_order_item_price(
    product_id: str,
    data: OrderItemPriceUpdate,
    order: BusinessOrder = Depends(load_seller_order),
):
    try:
        order.update_item_price(product_id, data.unit_price)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return order.view_order()




@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=201
)
def create_customer(
    data: CustomerCreate,
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db_write() as db:
        customer = CustomerRow(
            inventory_id=inventory_id,
            name=data.name,
            phone=data.phone,
            address=data.address
        )

        db.add(customer)
        db.flush()

        response = CustomerResponse.model_validate(customer)

    return response


@router.get(
    "/customers",
    response_model=list[CustomerResponse]
)
def list_customers(
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        customers = db.scalars(
            select(CustomerRow)
            .where(CustomerRow.inventory_id == inventory_id)
            .order_by(CustomerRow.name, CustomerRow.id)
        ).all()

        return [
            CustomerResponse.model_validate(customer)
            for customer in customers
        ]


@router.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse
)
def view_customer(
    customer_id: int,
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        customer = db.scalar(
            select(CustomerRow).where(
                CustomerRow.id == customer_id,
                CustomerRow.inventory_id == inventory_id
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        return CustomerResponse.model_validate(customer)


@router.patch(
    "/customers/{customer_id}",
    response_model=CustomerResponse
)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    inventory_id: int = Depends(get_seller_inventory)
):
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one field to update"
        )

    if "name" in changes and changes["name"] is None:
        raise HTTPException(
            status_code=422,
            detail="Name cannot be null"
        )

    with get_db_write() as db:
        customer = db.scalar(
            select(CustomerRow).where(
                CustomerRow.id == customer_id,
                CustomerRow.inventory_id == inventory_id
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        for field, value in changes.items():
            setattr(customer, field, value)

        db.flush()
        response = CustomerResponse.model_validate(customer)

    return response



# this creates  order for an offline customer for the seller .

@router.post(
    "/customers/{customer_id}/orders",
    response_model=OrderConfirmationResponse,
    status_code=201
)
def create_customer_order(
    customer_id: int,
    data: OrderItemsAdd,
    inventory_id: int = Depends(get_seller_inventory)
):
    with get_db() as db:
        customer = db.scalar(
            select(CustomerRow).where(
                CustomerRow.id == customer_id,
                CustomerRow.inventory_id == inventory_id
            )
        )

        if customer is None:
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

    items = [
        (item.product_id, item.quantity)
        for item in data.items
    ]

    try:
        order = BusinessOrder(
            inventory=Inventory(inventory_id),
            directory_customer_id=customer_id
        )
        result = order.confirmed_order(items)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if result["order_id"] is None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "No items could be accepted",
                "rejected": result["rejected"]
            }
        )

    return result










@router.post("/register", response_model=SellerResponse, status_code=201)
def register_seller(data: SellerCreate):
    inventory_name = data.inventory_name.strip()

    if not inventory_name:
        raise HTTPException(
            status_code=422,
            detail="Inventory name cannot be blank"
        )

    password_hash = hash_password(data.password)

    with get_db_write() as db:
        existing = db.scalar(
            select(UserRow).where(UserRow.username == data.username)
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Username already exists"
            )

        user = UserRow(
            username=data.username,
            password_hash=password_hash
        )
        inventory = InventoryRow(name=inventory_name)

        db.add_all([user, inventory])
        db.flush()

        db.add(
            InventorySellerRow(
                inventory_id=inventory.id,
                user_id=user.id
            )
        )

        response = SellerResponse(
            id=user.id,
            username=user.username,
            inventory_id=inventory.id,
            inventory_name=inventory.name
        )

    return response


@router.post("/login", response_model=TokenResponse)
def login_seller(data: UserLogin):
    with get_db() as db:
        user = db.scalar(
            select(UserRow).where(UserRow.username == data.username)
        )

        user_id = user.id if user is not None else None
        stored_hash = (
            user.password_hash if user is not None else DUMMY_HASH
        )

        inventory_id = None

        if user is not None:
            inventory_id = db.scalar(
                select(InventorySellerRow.inventory_id)
                .where(InventorySellerRow.user_id == user.id)
            )

    valid_password = verify_password(data.password, stored_hash)

    if user_id is None or not valid_password or inventory_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid seller credentials"
        )

    return TokenResponse(
        access_token=create_access_token(user_id)
    )
