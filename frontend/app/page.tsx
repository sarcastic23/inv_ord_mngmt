"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type Profile = { id: number; username: string; inventory_id: number; inventory_name: string };
type Product = { id: string; name: string; stock: number; unit_price: number };
type Customer = { id: number; inventory_id: number; name: string; phone: string | null; address: string | null };
type CustomerType = "directory" | "account";
type OrderStatus = "confirmed" | "delivered" | "cancelled";
type StockFilter = "all" | "low" | "finished";
type OrderGroup = {
  customer_type: CustomerType;
  customer_id: number;
  customer_name: string;
  phone: string | null;
  address: string | null;
  total_orders: number;
  confirmed_orders: number;
  delivered_orders: number;
  cancelled_orders: number;
  latest_order_id: number;
};
type Order = {
  order_id: number;
  inventory_id: number;
  customer_id: number | null;
  directory_customer_id: number | null;
  status: OrderStatus;
  total: number;
  items: { product_id: string; name: string; quantity: number; unit_price: number; subtotal: number }[];
};
type BillLine = { product_id: string; name: string; unit_price: number; quantity: number; subtotal: number; order_ids: number[] };
type OrderHistory = {
  customer: OrderGroup;
  status: OrderStatus;
  page: number;
  page_size: number;
  total: number;
  page_count: number;
  orders: Order[];
};
type Invoice = { id: number; invoice_number: string; customer_name: string; customer_phone: string | null; customer_address: string | null; seller_name: string; payment_terms: "due_on_receipt" | "credit"; issued_at: string; is_vat_invoice: boolean; subtotal: number; vat_total: number; total: number; amount_paid: number; balance: number; payment_status: "unpaid" | "partially_paid" | "paid"; items: { product_id: string; product_name: string; quantity: number; unit_price: number; subtotal: number; vat_rate_bps: number; vat_amount: number; total: number }[] };
type AnalysisProduct = { product_id: string; product_name: string; stock: number; units_sold: number; units_previous_period: number; sales_value: number; units_per_day: number; stock_days_remaining: number | null; change_percent: number | null; last_sold_at: string | null };
type AnalysisCustomer = { customer_key: string; customer_name: string; invoice_count: number; sales_value: number; units_purchased: number; sales_current_period: number; sales_previous_period: number; period_invoice_count: number; outstanding_balance: number; last_purchase_at: string | null; average_days_to_pay: number | null; settled_invoice_count: number; change_percent: number | null };
type AnalysisCustomerTrend = { customer_key: string; customer_name: string; sales_by_bucket: number[] };
type AnalysisData = { days: number; as_of: string; coverage: string; summary: { sales_value: number; units_sold: number; invoice_count: number; outstanding_balance: number; payments_received: number }; products: AnalysisProduct[]; customers: AnalysisCustomer[]; customer_trends: { bucket_days: number; labels: string[]; customers: AnalysisCustomerTrend[] } };
type AnalysisTab = "Products" | "Customers";
type Section = "Overview" | "Inventory" | "Customers" | "Orders" | "Invoices" | "Analysis";

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), Authorization: `Bearer ${token}`, ...init.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function money(value: number) { return `NPR ${new Intl.NumberFormat("en-IN", { minimumFractionDigits: Number.isInteger(value) ? 0 : 2, maximumFractionDigits: 2 }).format(value)}`; }
function initials(name: string) { return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase(); }
function orderCustomerKey(type: CustomerType, id: number) { return `${type}:${id}`; }

function TopCustomerTrendChart({ labels, customers }: { labels: string[]; customers: AnalysisCustomerTrend[] }) {
  const width = 820;
  const height = 300;
  const left = 66;
  const right = 18;
  const top = 18;
  const bottom = 42;
  const colors = ["#67b989", "#e4a75b", "#75a9ef", "#c38ce3", "#e77f81", "#56c5c6", "#c2c964", "#e38fbd", "#9caaa2"];
  const cumulativeByCustomer = customers.map((customer) => {
    let running = 0;
    return { ...customer, cumulative: customer.sales_by_bucket.map((value) => (running += value)) };
  });
  const ranksByBucket = labels.map((_, index) => [...cumulativeByCustomer]
    .filter((customer) => customer.cumulative[index] > 0)
    .sort((a, b) => b.cumulative[index] - a.cumulative[index] || a.customer_name.localeCompare(b.customer_name))
    .slice(0, 5)
    .map((customer) => customer.customer_key));
  const visibleKeys = new Set(ranksByBucket.flat());
  const currentTopFive = cumulativeByCustomer
    .filter((customer) => customer.cumulative.at(-1)! > 0)
    .sort((a, b) => b.cumulative.at(-1)! - a.cumulative.at(-1)! || a.customer_name.localeCompare(b.customer_name))
    .slice(0, 5);
  const maximum = Math.max(1, ...cumulativeByCustomer.flatMap((customer, customerIndex) => customer.cumulative.map((value, bucketIndex) => ranksByBucket[bucketIndex].includes(customers[customerIndex].customer_key) ? value : 0)));
  const x = (index: number) => left + (labels.length <= 1 ? 0 : index * (width - left - right) / (labels.length - 1));
  const y = (value: number) => height - bottom - value / maximum * (height - top - bottom);
  const linePath = (values: number[], key: string) => {
    let drawing = false;
    return values.map((value, index) => {
      if (!ranksByBucket[index].includes(key)) { drawing = false; return ""; }
      const command = drawing ? "L" : "M";
      drawing = true;
      return `${command}${x(index)},${y(value)}`;
    }).filter(Boolean).join(" ");
  };
  const shown = cumulativeByCustomer.filter((customer) => visibleKeys.has(customer.customer_key));

  if (!labels.length || !shown.length) return <Empty text="No customer sales to compare yet" detail="Saved invoices will build customer trends here." />;

  return <div className="customer-trend">
    <div className="customer-trend-heading"><div><span className="eyebrow muted">CUSTOMER RANKING · RUNNING TOTAL</span><h4>Top five customers over time</h4></div><small>Customers enter or leave the lines as their rank changes.</small></div>
    <div className="customer-trend-scroll"><svg className="customer-trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Running sales total for customers ranked in the top five at each point in time">
      {[0, 1, 2, 3, 4].map((step) => { const value = maximum * step / 4; const gridY = y(value); return <g key={step}><line x1={left} x2={width - right} y1={gridY} y2={gridY} className="chart-gridline" /><text x={left - 10} y={gridY + 4} textAnchor="end" className="chart-label">{money(value)}</text></g>; })}
      {shown.map((customer) => { const original = customers.find((row) => row.customer_key === customer.customer_key)!; const color = colors[customers.indexOf(original) % colors.length]; return <g key={customer.customer_key}><path d={linePath(customer.cumulative, customer.customer_key)} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />{customer.cumulative.map((value, index) => ranksByBucket[index].includes(customer.customer_key) ? <circle key={index} cx={x(index)} cy={y(value)} r="4" fill={color}><title>{customer.customer_name}: {money(value)} · {labels[index]}</title></circle> : null)}</g>; })}
      {labels.map((label, index) => <text key={label} x={x(index)} y={height - 13} textAnchor="middle" className="chart-label">{new Date(`${label}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</text>)}
    </svg></div>
    <div className="customer-trend-legend" aria-label="Current top five customers">{currentTopFive.map((customer, index) => <span key={customer.customer_key}><i style={{ background: colors[customers.findIndex((row) => row.customer_key === customer.customer_key) % colors.length] }} />{index + 1}. {customer.customer_name}</span>)}</div>
  </div>;
}

export default function Home() {
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [section, setSection] = useState<Section>("Overview");
  const [products, setProducts] = useState<Product[]>([]);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [orderGroups, setOrderGroups] = useState<OrderGroup[]>([]);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [analysisDays, setAnalysisDays] = useState<30 | 90>(30);
  const [analysisTab, setAnalysisTab] = useState<AnalysisTab>("Products");
  const [analysisSort, setAnalysisSort] = useState<"sales" | "balance" | "payment">("sales");
  const [analysisError, setAnalysisError] = useState("");
  const [analysisVersion, setAnalysisVersion] = useState(0);
  const [analysisLoadedKey, setAnalysisLoadedKey] = useState("");
  const [printingInvoice, setPrintingInvoice] = useState<Invoice | null>(null);
  const [vatInvoice, setVatInvoice] = useState(false);
  const [paymentTerms, setPaymentTerms] = useState<"due_on_receipt" | "credit">("credit");
  const [stockFilter, setStockFilter] = useState<StockFilter>("all");
  const [selectedOrderCustomer, setSelectedOrderCustomer] = useState<OrderGroup | null>(null);
  const [selectedOrderIds, setSelectedOrderIds] = useState<Set<number>>(new Set());
  const [historyStatus, setHistoryStatus] = useState<OrderStatus>("confirmed");
  const [historyPage, setHistoryPage] = useState(1);
  const [history, setHistory] = useState<OrderHistory | null>(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [deliveringBatch, setDeliveringBatch] = useState(false);

  const refresh = useCallback(async (auth: string, who: Profile) => {
    setLoading(true);
    setError("");
    try {
      const [stock, people, groups, recent, savedInvoices] = await Promise.all([
        fetch(`${API}/inventories/${who.inventory_id}/products`).then(async (response) => {
          if (!response.ok) throw new Error("Could not load inventory");
          return response.json() as Promise<Product[]>;
        }),
        request<Customer[]>("/seller/customers", auth),
        request<OrderGroup[]>("/seller/order-customers", auth),
        request<Order[]>("/seller/orders/recent", auth),
        request<Invoice[]>("/seller/invoices", auth),
      ]);
      setProducts(stock);
      setCustomers(people);
      setOrderGroups(groups);
      setRecentOrders(recent);
      setInvoices(savedInvoices);
      setAnalysisVersion((version) => version + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load your workspace");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("stockroom-theme");
    document.documentElement.dataset.theme = savedTheme === "dark" ? "dark" : "light";
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem("stockroom-token");
    if (!stored) return;
    request<Profile>("/seller/me", stored)
      .then((who) => {
        setToken(stored);
        setProfile(who);
        return refresh(stored, who);
      })
      .catch(() => window.localStorage.removeItem("stockroom-token"));
  }, [refresh]);

  useEffect(() => {
    if (!token || !selectedOrderCustomer) return;
    let active = true;
    const params = new URLSearchParams({ status: historyStatus, page: String(historyPage) });
    request<OrderHistory>(
      `/seller/order-customers/${selectedOrderCustomer.customer_type}/${selectedOrderCustomer.customer_id}/orders?${params}`,
      token,
    )
      .then((result) => { if (active) setHistory(result); })
      .catch((cause) => {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Could not load customer orders");
        setHistory({ customer: selectedOrderCustomer, status: historyStatus, page: historyPage, page_size: 5, total: 0, page_count: 1, orders: [] });
      });
    return () => { active = false; };
  }, [token, selectedOrderCustomer, historyStatus, historyPage, historyVersion]);

  useEffect(() => {
    if (!token || (section !== "Analysis" && section !== "Overview")) return;
    let active = true;
    const requestKey = `${analysisDays}:${analysisVersion}`;
    request<AnalysisData>(`/seller/analysis?days=${analysisDays}`, token)
      .then((data) => { if (active) { setAnalysisData(data); setAnalysisError(""); setAnalysisLoadedKey(requestKey); } })
      .catch((cause) => { if (active) setAnalysisError(cause instanceof Error ? cause.message : "Could not load analysis"); });
    return () => { active = false; };
  }, [token, section, analysisDays, analysisVersion]);

  const activeOrders = useMemo(
    () => orderGroups.reduce((sum, group) => sum + group.confirmed_orders, 0),
    [orderGroups],
  );
  const totalUnits = useMemo(() => products.reduce((sum, item) => sum + item.stock, 0), [products]);
  const filteredProducts = useMemo(() => {
    if (stockFilter === "low") return products.filter((item) => item.stock > 0 && item.stock < 10);
    if (stockFilter === "finished") return products.filter((item) => item.stock === 0);
    return products;
  }, [products, stockFilter]);
  const selectedOrders = useMemo(() => {
    if (!history || history.status !== "confirmed") return [];
    return history.orders.filter((order) => selectedOrderIds.has(order.order_id));
  }, [history, selectedOrderIds]);
  const billLines = useMemo(() => {
    const lines = new Map<string, BillLine>();
    for (const order of selectedOrders) {
      for (const item of order.items) {
        const key = `${item.product_id}:${item.unit_price}`;
        const line = lines.get(key);
        if (line) {
          line.quantity += item.quantity;
          line.subtotal += item.subtotal;
          if (!line.order_ids.includes(order.order_id)) line.order_ids.push(order.order_id);
        } else {
          lines.set(key, {
            product_id: item.product_id,
            name: item.name,
            unit_price: item.unit_price,
            quantity: item.quantity,
            subtotal: item.subtotal,
            order_ids: [order.order_id],
          });
        }
      }
    }
    return [...lines.values()];
  }, [selectedOrders]);
  const selectedBillTotal = useMemo(
    () => selectedOrders.reduce((sum, order) => sum + order.total, 0),
    [selectedOrders],
  );
  const lowStockCount = products.filter((item) => item.stock > 0 && item.stock < 10).length;
  const finishedCount = products.filter((item) => item.stock === 0).length;
  const analysisLoading = (section === "Analysis" || section === "Overview") && !analysisError && analysisLoadedKey !== `${analysisDays}:${analysisVersion}`;
  const sortedAnalysisCustomers = useMemo(() => {
    const rows = [...(analysisData?.customers || [])];
    rows.sort((a, b) => analysisSort === "balance"
      ? b.outstanding_balance - a.outstanding_balance
      : analysisSort === "payment"
        ? (a.average_days_to_pay ?? Number.POSITIVE_INFINITY) - (b.average_days_to_pay ?? Number.POSITIVE_INFINITY)
        : b.sales_value - a.sales_value);
    return rows;
  }, [analysisData, analysisSort]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoginBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API}/seller/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Login failed");
      const auth = body.access_token as string;
      const who = await request<Profile>("/seller/me", auth);
      window.localStorage.setItem("stockroom-token", auth);
      setToken(auth);
      setProfile(who);
      setSection("Overview");
      await refresh(auth, who);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in");
    } finally {
      setLoginBusy(false);
    }
  }

  function signOut() {
    window.localStorage.removeItem("stockroom-token");
    setToken(""); setProfile(null); setProducts([]); setCustomers([]);
    setOrderGroups([]); setRecentOrders([]); setHistory(null);
    setSelectedOrderIds(new Set());
  }

  function toggleTheme() {
    const root = document.documentElement;
    const theme = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = theme;
    window.localStorage.setItem("stockroom-theme", theme);
  }

  function flash(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3200);
  }

  async function addCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await request<Customer>("/seller/customers", token, {
        method: "POST",
        body: JSON.stringify({ name: form.get("name"), phone: form.get("phone") || null, address: form.get("address") || null }),
      });
      formElement.reset();
      await refresh(token, profile);
      flash("Customer added");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add customer");
    }
  }

  async function saveInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const id = String(form.get("id")).trim();
    const name = String(form.get("name")).trim();
    const stock = Number(form.get("stock"));
    const unit_price = Number(form.get("price"));
    try {
      if (editingProduct) {
        await request(`/inventories/${profile.inventory_id}/products/${encodeURIComponent(id)}`, token, {
          method: "PATCH",
          body: JSON.stringify({ name, stock, unit_price }),
        });
      } else {
        const updated = [...products.filter((item) => item.id !== id), { id, name, stock, unit_price }];
        await request(`/inventories/${profile.inventory_id}/products`, token, {
          method: "PUT",
          body: JSON.stringify(updated),
        });
      }
      formElement.reset();
      setEditingProduct(null);
      await refresh(token, profile);
      flash(editingProduct ? "Product updated" : "Inventory saved");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save inventory");
    }
  }

  function beginProductEdit(product: Product) {
    setEditingProduct(product);
    window.setTimeout(() => document.querySelector(".inventory-form")?.scrollIntoView({ behavior: "smooth", block: "center" }), 0);
  }

  async function createOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const customerId = Number(form.get("customer"));
    const productId = String(form.get("product"));
    const quantity = Number(form.get("quantity"));
    try {
      const result = await request<{ order_id: number; rejected: { product_id: string; message: string }[] }>(
        `/seller/customers/${customerId}/orders`,
        token,
        { method: "POST", body: JSON.stringify({ items: [{ product_id: productId, quantity }] }) },
      );
      formElement.reset();
      await refresh(token, profile);
      const existingGroup = orderGroups.find((item) => item.customer_type === "directory" && item.customer_id === customerId);
      const customer = customers.find((item) => item.id === customerId);
      if (existingGroup || customer) {
        const baseGroup: OrderGroup = existingGroup || {
          customer_type: "directory",
          customer_id: customer!.id,
          customer_name: customer!.name,
          phone: customer!.phone,
          address: customer!.address,
          total_orders: 0,
          confirmed_orders: 0,
          delivered_orders: 0,
          cancelled_orders: 0,
          latest_order_id: result.order_id,
        };
        setSelectedOrderCustomer({
          ...baseGroup,
          total_orders: baseGroup.total_orders + 1,
          confirmed_orders: baseGroup.confirmed_orders + 1,
          latest_order_id: result.order_id,
        });
      }
      setHistoryStatus("confirmed");
      setHistoryPage(1);
      setSection("Orders");
      setHistoryVersion((version) => version + 1);
      flash(result.rejected.length ? `Order #${result.order_id} created with unavailable items rejected` : `Order #${result.order_id} created`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create order");
    }
  }

  async function deliver(orderId: number) {
    if (!profile) return;
    try {
      await request(`/seller/orders/${orderId}/deliver`, token, { method: "POST" });
      await refresh(token, profile);
      setSelectedOrderIds((previous) => { const next = new Set(previous); next.delete(orderId); return next; });
      setHistoryVersion((version) => version + 1);
      flash(`Order #${orderId} marked delivered`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update order");
    }
  }

  async function deliverSelectedOrders() {
    if (!profile || !selectedOrderCustomer || selectedOrders.length === 0) return;
    setDeliveringBatch(true);
    const orderIds = selectedOrders.map((order) => order.order_id);
    try {
      const result = await request<{ order_ids: number[]; status: "delivered"; invoice_number: string }>("/seller/orders/deliver-batch", token, {
        method: "POST",
        body: JSON.stringify({ order_ids: orderIds, vat_rate_bps: vatInvoice ? 1300 : 0, payment_terms: paymentTerms }),
      });
      setSelectedOrderIds(new Set());
      await refresh(token, profile);
      setSelectedOrderIds(new Set());
      setHistoryStatus("delivered");
      setHistoryPage(1);
      setHistoryVersion((version) => version + 1);
      flash(`${result.invoice_number} saved; ${orderIds.length} orders delivered together`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not deliver selected orders");
    } finally {
      setDeliveringBatch(false);
    }
  }

  async function recordPayment(invoice: Invoice) {
    const amount = Number(window.prompt(`Payment received (balance ${money(invoice.balance)}):`));
    if (!Number.isFinite(amount) || amount <= 0) return;
    if (Math.abs(amount * 100 - Math.round(amount * 100)) > 1e-8) { setError("Enter an amount with no more than two decimal places"); return; }
    const method = window.prompt("Payment method (optional, e.g. cash or bank transfer):")?.trim() || null;
    const reference = window.prompt("Payment reference (optional):")?.trim() || null;
    try {
      await request(`/seller/invoices/${invoice.id}/payments`, token, { method: "POST", body: JSON.stringify({ amount, paid_at: new Date().toISOString(), method, reference }) });
      if (profile) await refresh(token, profile);
      flash(`Payment added to ${invoice.invoice_number}`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not record payment"); }
  }

  async function exportInvoices() {
    const response = await fetch(`${API}/seller/invoices/export`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) { setError("Could not export transactions"); return; }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a"); link.href = url; link.download = "distributor-transactions.xlsx"; link.click(); URL.revokeObjectURL(url);
  }

  async function updateOrderPrice(event: FormEvent<HTMLFormElement>, orderId: number, productId: string) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const unitPrice = Number(form.get("unit_price"));
    try {
      await request<Order>(`/seller/orders/${orderId}/items/${encodeURIComponent(productId)}/price`, token, {
        method: "PATCH",
        body: JSON.stringify({ unit_price: unitPrice }),
      });
      await refresh(token, profile!);
      setHistoryVersion((version) => version + 1);
      flash(`Price updated for order #${orderId}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update order price");
    }
  }

  function openCustomerOrders(customer: OrderGroup) {
    setSelectedOrderCustomer(customer);
    setSelectedOrderIds(new Set());
    setHistoryStatus("confirmed");
    setHistoryPage(1);
    setHistory(null);
  }

  if (!token || !profile) {
    return <main className="login-shell">
      <div className="login-art">
        <div className="brand"><span className="brand-mark">s</span> stockroom</div>
        <div className="art-copy"><span className="eyebrow">DISTRIBUTOR WORKSPACE</span><h1>Your whole operation,<br />in one place.</h1><p>Keep stock moving, customers close, and orders on track.</p><div className="art-stats"><div><strong>01</strong><span>Inventory</span></div><div><strong>02</strong><span>Customers</span></div><div><strong>03</strong><span>Orders</span></div></div></div>
        <span className="art-note">A clearer way to run your business.</span>
      </div>
      <div className="login-panel">
        <button type="button" className="theme-toggle login-theme-toggle" onClick={toggleTheme} aria-label="Toggle color theme" title="Toggle color theme"><span aria-hidden="true">◐</span><span>Theme</span></button>
        <form className="login-form" onSubmit={login}><span className="eyebrow muted">WELCOME BACK</span><h2>Sign in to your<br />workspace</h2><p className="subtext">Use your distributor account to continue.</p>{error && <div className="alert">{error}</div>}<label>Username<input required name="username" autoComplete="username" placeholder="Your username" /></label><label>Password<input required name="password" type="password" autoComplete="current-password" placeholder="Your password" /></label><button className="primary-button full" disabled={loginBusy}>{loginBusy ? "Signing in…" : "Sign in"}<span>↗</span></button><p className="login-hint">Need an account? Ask your administrator to set one up.</p></form>
        <span className="login-footer">STOCKROOM · DISTRIBUTOR OPERATIONS</span>
      </div>
    </main>;
  }

  const nav: Section[] = ["Overview", "Inventory", "Customers", "Orders", "Invoices", "Analysis"];
  const selectedHistoryCustomer = selectedOrderCustomer;
  const statusSummary = history?.customer || selectedHistoryCustomer;
  const historyLoading = Boolean(selectedHistoryCustomer && (
    !history
    || history.status !== historyStatus
    || history.page !== (historyStatus === "confirmed" ? 1 : historyPage)
    || history.customer.customer_type !== selectedHistoryCustomer.customer_type
    || history.customer.customer_id !== selectedHistoryCustomer.customer_id
  ));
  const statusCounts = statusSummary ? {
    confirmed: statusSummary.confirmed_orders,
    delivered: statusSummary.delivered_orders,
    cancelled: statusSummary.cancelled_orders,
  } : { confirmed: 0, delivered: 0, cancelled: 0 };
  return <main className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">s</span> stockroom</div>
      <div className="workspace-label">WORKSPACE</div>
      <div className="workspace-card"><div className="workspace-icon">{initials(profile.inventory_name)}</div><div className="workspace-text"><strong>{profile.inventory_name}</strong><span>Distributor account</span></div><span className="chevron">⌄</span></div>
      <nav className="side-nav">{nav.map((item, index) => <button key={item} className={`nav-item ${section === item ? "selected" : ""}`} onClick={() => setSection(item)}><span className="nav-icon">{["◫", "▦", "♧", "↗", "▤", "▥"][index]}</span>{item}{item === "Orders" && activeOrders > 0 && <span className="nav-count">{activeOrders}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon">?</div><strong>Need a hand?</strong><span>Your workspace is ready whenever you are.</span></div><button className="account-button" onClick={signOut}><span className="avatar">{initials(profile.username)}</span><span className="account-name"><strong>{profile.username}</strong><small>Distributor</small></span><span className="signout">↗</span></button></div>
    </aside>

    <section className="main-area">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><i>/</i><strong>{section}</strong></div><div className="top-actions"><button type="button" className="theme-toggle" onClick={toggleTheme} aria-label="Toggle color theme" title="Toggle color theme"><span aria-hidden="true">◐</span><span>Theme</span></button><span className="live-dot">●</span><span className="connected">All changes synced</span><button className="top-avatar" title={profile.username}>{initials(profile.username)}</button></div></header>
      <div className="content">
        <div className="page-heading"><div><span className="eyebrow muted">{section === "Overview" ? "YOUR BUSINESS AT A GLANCE" : `${profile.inventory_name.toUpperCase()} · OPERATIONS`}</span><h1>{section === "Overview" ? <>Good to see you, {profile.username}.</> : section}</h1><p>{section === "Overview" ? "Here’s what’s happening across your distributor workspace today." : section === "Inventory" ? "Keep product availability and pricing up to date." : section === "Customers" ? "Manage the people and businesses you supply." : section === "Invoices" ? "Review bills, record customer payments, and export your records." : section === "Analysis" ? "See sales movement, customer buying patterns, and payment pace." : "Browse orders by customer and track each delivery."}</p></div>{section === "Overview" && <div className="date-chip"><span>◷</span> Workspace overview</div>}</div>
        {error && <div className="alert page-alert"><span>{error}</span><button onClick={() => setError("")}>×</button></div>}
        {notice && <div className="toast">✓ &nbsp;{notice}</div>}
        {loading && <div className="loading-line"><span /> Updating workspace…</div>}

        {section === "Overview" && <>
          <div className="metric-grid"><Metric icon="▦" label="Products in stock" value={products.length.toString()} note={`${totalUnits.toLocaleString()} total units available`} tone="lavender" /><Metric icon="♧" label="Your customers" value={customers.length.toString()} note="Saved customer profiles" tone="peach" /><Metric icon="↗" label="Open orders" value={activeOrders.toString()} note="Confirmed and awaiting delivery" tone="mint" /></div>
          <div className="overview-grid">
            <div className="panel inventory-panel"><div className="panel-heading"><div><span className="eyebrow muted">STOCK OVERVIEW</span><h3>Inventory snapshot</h3></div><button className="text-button" onClick={() => setSection("Inventory")}>View inventory <span>→</span></button></div>{products.length ? <div className="table-wrap"><table><thead><tr><th>PRODUCT</th><th>UNIT PRICE</th><th>IN STOCK</th><th>STATUS</th></tr></thead><tbody>{products.slice(0, 5).map((item) => <tr key={item.id}><td><div className="product-cell"><span className="product-dot">{initials(item.name)}</span><span><strong>{item.name}</strong><small>{item.id}</small></span></div></td><td>{money(item.unit_price)}</td><td>{item.stock}</td><td><StockStatus count={item.stock} /></td></tr>)}</tbody></table></div> : <Empty text="Your inventory is empty" detail="Add products to start managing stock." action="Add a product" onClick={() => setSection("Inventory")} />}</div>
            <div className="panel activity-panel"><div className="panel-heading"><div><span className="eyebrow muted">LATEST ACTIVITY</span><h3>Recent orders</h3></div><button className="icon-button" onClick={() => setSection("Orders")}>↗</button></div>{recentOrders.map((order) => <OrderRow key={order.order_id} order={order} customer={orderGroups.find((group) => (order.directory_customer_id != null && group.customer_type === "directory" && group.customer_id === order.directory_customer_id) || (order.customer_id != null && group.customer_type === "account" && group.customer_id === order.customer_id))} />)}{!recentOrders.length && <Empty text="No orders yet" detail="Orders you create will show up here." action="Create an order" onClick={() => setSection("Orders")} />}</div>
          </div>
          <div className="panel overview-customer-trends"><div className="panel-heading"><div><span className="eyebrow muted">CUSTOMER PERFORMANCE · LAST {analysisDays} DAYS</span><h3>Top five customers</h3></div><button className="text-button" onClick={() => setSection("Analysis")}>Open analysis <span>→</span></button></div>{analysisError ? <div className="alert">{analysisError}</div> : analysisLoading || !analysisData ? <div className="loading-line"><span /> Loading customer trends…</div> : <TopCustomerTrendChart labels={analysisData.customer_trends.labels} customers={analysisData.customer_trends.customers} />}</div>
        </>}

        {section === "Inventory" && <div className="section-grid">
          <div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">PRODUCT CATALOG</span><h3>Inventory</h3></div><span className="count-pill">{filteredProducts.length} shown</span></div>
            <div className="filter-bar" role="group" aria-label="Filter inventory by stock status">
              <button className={`filter-chip ${stockFilter === "all" ? "active" : ""}`} onClick={() => setStockFilter("all")}>All <span>{products.length}</span></button>
              <button className={`filter-chip ${stockFilter === "low" ? "active" : ""}`} onClick={() => setStockFilter("low")}>Running low <span>{lowStockCount}</span></button>
              <button className={`filter-chip ${stockFilter === "finished" ? "active" : ""}`} onClick={() => setStockFilter("finished")}>Finished <span>{finishedCount}</span></button>
            </div>
            {filteredProducts.length ? <div className="table-wrap"><table><thead><tr><th>PRODUCT</th><th>ID</th><th>PRICE</th><th>STOCK</th><th>AVAILABILITY</th><th>ACTION</th></tr></thead><tbody>{filteredProducts.map((item) => <tr key={item.id}><td><strong>{item.name}</strong></td><td className="mono">{item.id}</td><td>{money(item.unit_price)}</td><td>{item.stock}</td><td><StockStatus count={item.stock} /></td><td><button className="text-button" onClick={() => beginProductEdit(item)}>Edit</button></td></tr>)}</tbody></table></div> : <Empty text={products.length ? "No products in this stock filter" : "No products yet"} detail={products.length ? "Try another stock status." : "Add your first product using the form."} />}
          </div>
          <form className="panel form-panel inventory-form" key={editingProduct?.id ?? "new-product"} onSubmit={saveInventory}><span className="eyebrow muted">{editingProduct ? "EDIT INVENTORY ITEM" : "CATALOG UPDATE"}</span><h3>{editingProduct ? `Edit ${editingProduct.name}` : "Add or update a product"}</h3><p>{editingProduct ? "Update this product’s name, stock quantity, or unit price." : "Entering an existing product ID updates its stock and price."}</p><label>Product ID<input name="id" required readOnly={Boolean(editingProduct)} defaultValue={editingProduct?.id ?? ""} placeholder="e.g. coffee-250g" /></label><label>Product name<input name="name" required defaultValue={editingProduct?.name ?? ""} placeholder="e.g. House blend coffee" /></label><div className="field-row"><label>Stock quantity<input name="stock" type="number" min="0" required defaultValue={editingProduct?.stock ?? ""} placeholder="0" /></label><label>Unit price (NPR, whole rupees)<input name="price" type="number" min="0" step="1" required defaultValue={editingProduct?.unit_price ?? ""} placeholder="0" /></label></div><button className="primary-button">{editingProduct ? "Save changes" : "Save product"} <span>↗</span></button>{editingProduct && <button type="button" className="text-button cancel-edit-button" onClick={(event) => { event.currentTarget.form?.reset(); setEditingProduct(null); }}>Cancel edit</button>}<small className="form-footnote">VAT and invoice balances can include paisa; catalog prices remain whole rupees.</small></form>
        </div>}

        {section === "Customers" && <div className="section-grid"><div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">CUSTOMER DIRECTORY</span><h3>Your customers</h3></div><span className="count-pill">{customers.length} customers</span></div>{customers.length ? <div className="customer-list">{customers.map((person) => <div className="customer-row" key={person.id}><span className="customer-avatar">{initials(person.name)}</span><div className="customer-info"><strong>{person.name}</strong><span>{person.phone || "No phone added"}</span></div><div className="customer-address">{person.address || "—"}</div><span className="customer-id">#{person.id}</span></div>)}</div> : <Empty text="Your customer list is empty" detail="Add a customer to create orders for them." />}</div><form className="panel form-panel" onSubmit={addCustomer}><span className="eyebrow muted">NEW PROFILE</span><h3>Add a customer</h3><p>Save a contact to make placing their orders faster.</p><label>Customer name<input name="name" required maxLength={100} placeholder="Business or contact name" /></label><label>Phone number <span className="optional">OPTIONAL</span><input name="phone" maxLength={30} placeholder="(555) 000-0000" /></label><label>Address <span className="optional">OPTIONAL</span><textarea name="address" maxLength={300} rows={3} placeholder="Street, city, and delivery notes" /></label><button className="primary-button">Save customer <span>↗</span></button></form></div>}

        {section === "Orders" && <div className="section-grid orders-grid">
          <div className="panel orders-browser">
            {!selectedOrderCustomer ? <>
              <div className="panel-heading"><div><span className="eyebrow muted">CUSTOMER ORDERS</span><h3>Orders by customer</h3></div><span className="count-pill">{orderGroups.length} customers</span></div>
              {orderGroups.length ? <div className="customer-order-groups">{orderGroups.map((group) => <button key={orderCustomerKey(group.customer_type, group.customer_id)} className="customer-order-group" onClick={() => openCustomerOrders(group)}><span className="customer-avatar">{initials(group.customer_name)}</span><span className="customer-order-info"><strong>{group.customer_name}</strong><small>{group.customer_type === "account" ? "Online customer" : "Saved customer"} · {group.total_orders} {group.total_orders === 1 ? "order" : "orders"}</small><span className="group-status-counts"><span>{group.confirmed_orders} confirmed</span><span>{group.delivered_orders} delivered</span><span>{group.cancelled_orders} cancelled</span></span></span><span className="latest-order">Latest #{group.latest_order_id}</span><span className="group-open">View orders →</span></button>)}</div> : <Empty text="No customer orders yet" detail="Orders will be grouped here by customer." />}
            </> : <>
              <div className="history-heading"><button className="text-button back-button" onClick={() => { setSelectedOrderCustomer(null); setSelectedOrderIds(new Set()); setHistory(null); }}>← All customers</button><div className="history-customer"><span className="customer-avatar">{initials(selectedOrderCustomer.customer_name)}</span><div><span className="eyebrow muted">CUSTOMER ORDER HISTORY</span><h3>{selectedOrderCustomer.customer_name}</h3><small>{selectedOrderCustomer.customer_type === "account" ? "Online customer" : selectedOrderCustomer.phone || "Saved customer"}</small></div></div></div>
              <div className="history-tabs" role="tablist" aria-label="Order status"><button role="tab" aria-selected={historyStatus === "confirmed"} className={`history-tab ${historyStatus === "confirmed" ? "active" : ""}`} onClick={() => { setSelectedOrderIds(new Set()); setHistoryStatus("confirmed"); setHistoryPage(1); }}>Confirmed <span>{statusCounts.confirmed}</span></button><button role="tab" aria-selected={historyStatus === "delivered"} className={`history-tab ${historyStatus === "delivered" ? "active" : ""}`} onClick={() => { setSelectedOrderIds(new Set()); setHistoryStatus("delivered"); setHistoryPage(1); }}>Delivered <span>{statusCounts.delivered}</span></button><button role="tab" aria-selected={historyStatus === "cancelled"} className={`history-tab ${historyStatus === "cancelled" ? "active" : ""}`} onClick={() => { setSelectedOrderIds(new Set()); setHistoryStatus("cancelled"); setHistoryPage(1); }}>Cancelled <span>{statusCounts.cancelled}</span></button></div>
              <p className="history-note">{historyStatus === "confirmed" ? "All confirmed orders are shown, newest first." : `Showing up to 5 ${historyStatus} orders per page, newest first.`}</p>
              {historyLoading && <div className="loading-line"><span /> Loading customer orders…</div>}
              {!historyLoading && history?.orders.length ? <>
                {historyStatus === "confirmed" && <div className="bulk-order-toolbar"><span>Select confirmed orders to combine on one bill.</span><div><button onClick={() => setSelectedOrderIds(new Set(history.orders.map((order) => order.order_id)))}>Select all</button><button onClick={() => setSelectedOrderIds(new Set())}>Clear</button></div></div>}
                {selectedOrders.length > 0 && <BillPreview customer={selectedOrderCustomer.customer_name} orders={selectedOrders} lines={billLines} total={selectedBillTotal} vatInvoice={vatInvoice} onVatChange={setVatInvoice} paymentTerms={paymentTerms} onPaymentTermsChange={setPaymentTerms} delivering={deliveringBatch} onPrint={() => window.print()} onDeliver={deliverSelectedOrders} />}
                <div className="order-list">{history.orders.map((order) => <OrderCard key={order.order_id} order={order} selectable={historyStatus === "confirmed"} selected={selectedOrderIds.has(order.order_id)} onSelect={(orderId, checked) => setSelectedOrderIds((previous) => { const next = new Set(previous); if (checked) next.add(orderId); else next.delete(orderId); return next; })} onDeliver={deliver} onUpdatePrice={updateOrderPrice} />)}</div>
                {historyStatus !== "confirmed" && history.page_count > 1 && <div className="pagination-controls"><span>Showing {(history.page - 1) * history.page_size + 1}–{Math.min(history.page * history.page_size, history.total)} of {history.total}</span><div><button disabled={history.page <= 1} onClick={() => setHistoryPage((page) => Math.max(1, page - 1))}>← Previous</button><span>Page {history.page} of {history.page_count}</span><button disabled={history.page >= history.page_count} onClick={() => setHistoryPage((page) => Math.min(history.page_count, page + 1))}>Next →</button></div></div>}
              </> : !historyLoading && <Empty text={`No ${historyStatus} orders`} detail="Choose another status or create an order for this customer." />}
            </>}
          </div>
          <form className="panel form-panel" onSubmit={createOrder}><span className="eyebrow muted">NEW ORDER</span><h3>Create an order</h3><p>Choose a customer and add a product from your inventory.</p><label>Customer<select name="customer" required defaultValue=""><option value="" disabled>Select a customer</option>{customers.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label><label>Product<select name="product" required defaultValue=""><option value="" disabled>Select a product</option>{products.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.stock} in stock</option>)}</select></label><label>Quantity<input name="quantity" type="number" min="1" required placeholder="1" /></label><button className="primary-button" disabled={!customers.length || !products.length}>Create order <span>↗</span></button>{(!customers.length || !products.length) && <small className="form-footnote">Add at least one customer and one stocked product first.</small>}</form>
        </div>}

        {section === "Invoices" && <div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">TRANSACTION RECORD</span><h3>Invoices and payments</h3></div><button className="primary-button" onClick={exportInvoices}>Export Excel workbook</button></div><p className="history-note">One workbook contains Invoices, Invoice Items, and Payments sheets. Filter by customer or payment status in Excel.</p>{printingInvoice && <InvoicePrint invoice={printingInvoice} onClose={() => setPrintingInvoice(null)} onPrint={() => window.print()} />} {invoices.length ? <div className="table-wrap"><table><thead><tr><th>INVOICE</th><th>CUSTOMER</th><th>DATE</th><th>TYPE / TERMS</th><th>TOTAL</th><th>PAID</th><th>BALANCE / STATUS</th><th></th></tr></thead><tbody>{invoices.map((invoice) => <tr key={invoice.id}><td><strong>{invoice.invoice_number}</strong></td><td>{invoice.customer_name}</td><td>{new Date(invoice.issued_at).toLocaleDateString()}</td><td>{invoice.is_vat_invoice ? "VAT 13%" : "Standard"} · {invoice.payment_terms === "credit" ? "Credit" : "Due on receipt"}</td><td>{money(invoice.total)}</td><td>{money(invoice.amount_paid)}</td><td>{money(invoice.balance)} · {invoice.payment_status}</td><td><button className="text-button" onClick={() => setPrintingInvoice(invoice)}>View / print</button>{invoice.balance > 0 && <button className="text-button" onClick={() => recordPayment(invoice)}>Record payment</button>}</td></tr>)}</tbody></table></div> : <Empty text="No invoices yet" detail="Invoices are saved when you deliver an order or a combined customer bill." />}</div>}

        {section === "Analysis" && <div className="analysis-layout">
          <div className="analysis-toolbar"><div className="history-tabs" role="tablist" aria-label="Analysis section"><button role="tab" aria-selected={analysisTab === "Products"} className={`history-tab ${analysisTab === "Products" ? "active" : ""}`} onClick={() => setAnalysisTab("Products")}>Products</button><button role="tab" aria-selected={analysisTab === "Customers"} className={`history-tab ${analysisTab === "Customers" ? "active" : ""}`} onClick={() => setAnalysisTab("Customers")}>Customers</button></div><div className="history-tabs" role="group" aria-label="Analysis time period"><button className={`history-tab ${analysisDays === 30 ? "active" : ""}`} onClick={() => setAnalysisDays(30)}>Last 30 days</button><button className={`history-tab ${analysisDays === 90 ? "active" : ""}`} onClick={() => setAnalysisDays(90)}>Last 90 days</button></div></div>
          {analysisError && <div className="alert">{analysisError}</div>}
          {analysisLoading && <div className="loading-line"><span /> Calculating analysis…</div>}
          {!analysisLoading && analysisData && <>
            <div className="metric-grid"><Metric icon="↗" label={`Sales before VAT · ${analysisDays} days`} value={money(analysisData.summary.sales_value)} note={`${analysisData.summary.invoice_count} saved invoices`} tone="mint" /><Metric icon="▦" label="Units sold" value={analysisData.summary.units_sold.toLocaleString()} note={`Across ${analysisData.products.filter((product) => product.units_sold > 0).length} products`} tone="lavender" /><Metric icon="♧" label="Customer balances due" value={money(analysisData.summary.outstanding_balance)} note="Outstanding across saved invoices" tone="peach" /><Metric icon="✓" label={`Payments received · ${analysisDays} days`} value={money(analysisData.summary.payments_received)} note="Recorded customer payments" tone="lavender" /></div>
            <div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">{analysisTab === "Products" ? "PRODUCT MOVEMENT" : "CUSTOMER ACTIVITY"}</span><h3>{analysisTab === "Products" ? "Sales pace and stock cover" : "Purchase and payment patterns"}</h3></div>{analysisTab === "Customers" && <label className="analysis-sort">Rank by<select value={analysisSort} onChange={(event) => setAnalysisSort(event.currentTarget.value as "sales" | "balance" | "payment")}><option value="sales">Total purchases</option><option value="balance">Largest balance</option><option value="payment">Fastest average payment</option></select></label>}</div>
              <p className="history-note">Compared with the previous {analysisDays} days. Reports use invoices saved in this app; sales values exclude VAT. No profitability estimate is included.</p>
              {analysisTab === "Customers" && <TopCustomerTrendChart labels={analysisData.customer_trends.labels} customers={analysisData.customer_trends.customers} />}
              {analysisTab === "Products" ? analysisData.products.length ? <div className="table-wrap"><table><thead><tr><th>PRODUCT</th><th>IN STOCK</th><th>UNITS · {analysisDays} DAYS</th><th>AVG / DAY</th><th>STOCK COVER</th><th>CHANGE</th><th>SALES</th></tr></thead><tbody>{analysisData.products.map((product) => <tr key={product.product_id}><td><div className="product-cell"><span><strong>{product.product_name}</strong><small>{product.product_id}</small></span></div></td><td>{product.stock}</td><td>{product.units_sold}</td><td>{product.units_per_day}</td><td>{product.stock_days_remaining == null ? "—" : `${product.stock_days_remaining} days`}</td><td>{product.change_percent == null ? product.units_sold > 0 ? "New" : "—" : `${product.change_percent > 0 ? "+" : ""}${product.change_percent}%`}</td><td>{money(product.sales_value)}</td></tr>)}</tbody></table></div> : <Empty text="No product sales to analyze yet" detail="Saved invoices will build product sales history here." /> : sortedAnalysisCustomers.length ? <div className="table-wrap"><table><thead><tr><th>CUSTOMER</th><th>TOTAL PURCHASES</th><th>PERIOD SALES</th><th>CHANGE</th><th>INVOICES</th><th>AMOUNT DUE</th><th>AVG. DAYS TO PAY</th></tr></thead><tbody>{sortedAnalysisCustomers.map((customer) => <tr key={customer.customer_key}><td><strong>{customer.customer_name}</strong></td><td>{money(customer.sales_value)} · {customer.units_purchased} units</td><td>{money(customer.sales_current_period)}</td><td>{customer.change_percent == null ? customer.sales_current_period > 0 ? "New" : "—" : `${customer.change_percent > 0 ? "+" : ""}${customer.change_percent}%`}</td><td>{customer.period_invoice_count} · {customer.invoice_count} all time</td><td>{money(customer.outstanding_balance)}</td><td>{customer.average_days_to_pay == null ? "Not enough settled invoices" : `${customer.average_days_to_pay} days · ${customer.settled_invoice_count} settled`}</td></tr>)}</tbody></table></div> : <Empty text="No customer sales to analyze yet" detail="Customer rankings appear after invoices are saved." />}
            </div>
            <p className="analysis-footnote">Coverage starts with invoices saved in Stockroom. Orders delivered before invoice tracking are not included. Payment speed uses fully paid invoices only.</p>
          </>}
        </div>}
        <footer className="page-footer"><span>STOCKROOM</span><span>Distributor operations, made clearer.</span></footer>
      </div>
    </section>
  </main>;
}

function Metric({ icon, label, value, note, tone }: { icon: string; label: string; value: string; note: string; tone: string }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span><span className="metric-arrow">↗</span></div>;
}

function StockStatus({ count }: { count: number }) {
  return <span className={`stock-status ${count === 0 ? "out" : count < 10 ? "low" : "in"}`}><i />{count === 0 ? "Finished" : count < 10 ? "Running low" : "In stock"}</span>;
}

function StatusBadge({ status }: { status: OrderStatus }) {
  return <span className={`status-badge ${status}`}><i />{status}</span>;
}

function OrderRow({ order, customer }: { order: Order; customer?: OrderGroup }) {
  const customerName = customer?.customer_name || `Customer #${order.directory_customer_id ?? order.customer_id}`;
  return <div className="activity-row"><span className="activity-icon">↗</span><div className="activity-copy"><strong>{customerName}</strong><span>Order #{order.order_id} · {order.items.length} items</span></div><div className="activity-right"><strong>{money(order.total)}</strong><StatusBadge status={order.status} /></div></div>;
}

function OrderCard({ order, selectable = false, selected = false, onSelect, onDeliver, onUpdatePrice }: {
  order: Order;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (orderId: number, checked: boolean) => void;
  onDeliver: (orderId: number) => void;
  onUpdatePrice: (event: FormEvent<HTMLFormElement>, orderId: number, productId: string) => void;
}) {
  return <article className="order-card">
    <div className="order-card-top">{selectable && <label className="order-select"><input type="checkbox" checked={selected} onChange={(event) => onSelect?.(order.order_id, event.currentTarget.checked)} /><span>Bill</span></label>}<div className="order-mark">↗</div><div className="order-main"><strong>Order #{order.order_id}</strong><span>{order.items.length} line {order.items.length === 1 ? "item" : "items"}</span></div><StatusBadge status={order.status} /></div>
    <div className="order-detail-lines">{order.items.map((item) => <div className="order-detail-line" key={item.product_id}><div className="order-item-description"><strong>{item.name}</strong><span>{item.quantity} × {money(item.unit_price)} = {money(item.subtotal)}</span></div><form className="price-edit-form" onSubmit={(event) => onUpdatePrice(event, order.order_id, item.product_id)}><label>Customer price<input name="unit_price" type="number" min="0" step="1" defaultValue={item.unit_price} aria-label={`New unit price for ${item.name}`} /></label><button>Save price</button></form></div>)}</div>
    <div className="order-card-bottom"><span>Order total</span><strong>{money(order.total)}</strong>{order.status === "confirmed" && <button className="deliver-button" onClick={() => onDeliver(order.order_id)}>Mark delivered <span>→</span></button>}</div>
  </article>;
}

function BillPreview({ customer, orders, lines, total, vatInvoice, onVatChange, paymentTerms, onPaymentTermsChange, delivering, onPrint, onDeliver }: {
  customer: string;
  orders: Order[];
  lines: BillLine[];
  total: number;
  vatInvoice: boolean;
  onVatChange: (enabled: boolean) => void;
  paymentTerms: "due_on_receipt" | "credit";
  onPaymentTermsChange: (terms: "due_on_receipt" | "credit") => void;
  delivering: boolean;
  onPrint: () => void;
  onDeliver: () => void;
}) {
  const vat = vatInvoice ? orders.reduce((sum, order) => sum + order.items.reduce((orderTax, item) => orderTax + Math.round(item.subtotal * 13) / 100, 0), 0) : 0;
  return <section className="bill-preview" aria-label="Combined bill preview">
    <div className="bill-heading"><div><span className="eyebrow muted">BILL PREVIEW</span><h4>Combined customer bill</h4><p>{customer} · {new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date())}</p></div><strong>{orders.length} orders</strong></div>
    <p className="bill-order-refs">Includes orders {orders.map((order) => `#${order.order_id}`).join(", ")}</p>
    <div className="bill-lines">{lines.map((line) => <div className="bill-line" key={`${line.product_id}:${line.unit_price}`}><span><strong>{line.name}</strong><small>{line.quantity} × {money(line.unit_price)} · from {line.order_ids.map((id) => `#${id}`).join(", ")}</small></span><strong>{money(line.subtotal)}</strong></div>)}</div>
    <label className="vat-choice"><input type="checkbox" checked={vatInvoice} onChange={(event) => onVatChange(event.currentTarget.checked)} /> Issue VAT invoice at 13% <small>Use only when VAT registration and item tax treatment are confirmed.</small></label>
    <label className="terms-choice">Payment terms<select value={paymentTerms} onChange={(event) => onPaymentTermsChange(event.currentTarget.value as "due_on_receipt" | "credit")}><option value="credit">Credit (record payment later)</option><option value="due_on_receipt">Due on receipt (record payment)</option></select></label>
    {vatInvoice && <div className="bill-total"><span>VAT (13%)</span><strong>{money(vat)}</strong></div>}
    <div className="bill-total"><span>{vatInvoice ? "Total including VAT" : "Combined total"}</span><strong>{money(total + vat)}</strong></div>
    <div className="bill-actions"><button onClick={onPrint}>Print bill</button><button className="primary-button" disabled={delivering} onClick={onDeliver}>{delivering ? "Delivering…" : `Deliver ${orders.length} selected orders`}<span>↗</span></button></div>
    <small className="bill-note">Selected orders will be delivered together. This preview uses the order prices shown above.</small>
  </section>;
}

function InvoicePrint({ invoice, onClose, onPrint }: { invoice: Invoice; onClose: () => void; onPrint: () => void }) {
  return <section className="invoice-document">
    <div className="invoice-print-actions"><button onClick={onPrint}>Print invoice</button><button onClick={onClose}>Close</button></div>
    <div className="invoice-title"><div><span className="eyebrow muted">{invoice.is_vat_invoice ? "VAT BILL · 13%" : "SALES BILL"}</span><h2>{invoice.seller_name}</h2><p>{invoice.invoice_number} · {new Date(invoice.issued_at).toLocaleString()} · {invoice.payment_terms === "credit" ? "Credit" : "Due on receipt"}</p></div><strong>{invoice.invoice_number}</strong></div>
    <div className="invoice-parties"><div><small>SELLER</small><strong>{invoice.seller_name}</strong></div><div><small>BILL TO</small><strong>{invoice.customer_name}</strong><span>{invoice.customer_phone || ""}</span><span>{invoice.customer_address || ""}</span></div></div>
    <div className="table-wrap"><table><thead><tr><th>ITEM</th><th>QTY</th><th>UNIT PRICE</th><th>SUBTOTAL</th>{invoice.is_vat_invoice && <th>VAT</th>}<th>TOTAL</th></tr></thead><tbody>{invoice.items.map((item, index) => <tr key={`${item.product_id}-${index}`}><td>{item.product_name}</td><td>{item.quantity}</td><td>{money(item.unit_price)}</td><td>{money(item.subtotal)}</td>{invoice.is_vat_invoice && <td>{money(item.vat_amount)}</td>}<td>{money(item.total)}</td></tr>)}</tbody></table></div>
    <div className="invoice-sums"><span>Subtotal <strong>{money(invoice.subtotal)}</strong></span>{invoice.is_vat_invoice && <span>VAT (13%) <strong>{money(invoice.vat_total)}</strong></span>}<span>Total <strong>{money(invoice.total)}</strong></span><span>Paid <strong>{money(invoice.amount_paid)}</strong></span><span>Balance <strong>{money(invoice.balance)}</strong></span></div>
  </section>;
}

function Empty({ text, detail, action, onClick }: { text: string; detail: string; action?: string; onClick?: () => void }) {
  return <div className="empty-state"><span className="empty-icon">⌁</span><strong>{text}</strong><span>{detail}</span>{action && <button className="text-button" onClick={onClick}>{action} →</button>}</div>;
}
