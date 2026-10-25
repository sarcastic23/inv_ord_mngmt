"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type Profile = { id: number; username: string; inventory_id: number; inventory_name: string };
type Product = { id: string; name: string; stock: number; unit_price: number };
type Customer = { id: number; inventory_id: number; name: string; phone: string | null; address: string | null };
type OrderSummary = { order_id: number; inventory_id: number; status: "confirmed" | "cancelled" | "delivered" };
type Order = OrderSummary & { customer_id: number | null; directory_customer_id: number | null; total: number; items: { product_id: string; name: string; quantity: number; unit_price: number; subtotal: number }[] };
type Section = "Overview" | "Inventory" | "Customers" | "Orders";

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

function money(value: number) { return `${new Intl.NumberFormat("en-US").format(value)} units`; }
function initials(name: string) { return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase(); }

export default function Home() {
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [section, setSection] = useState<Section>("Overview");
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);

  const refresh = useCallback(async (auth: string, who: Profile) => {
    setLoading(true);
    setError("");
    try {
      const [stock, people, summaries] = await Promise.all([
        fetch(`${API}/inventories/${who.inventory_id}/products`).then(async (r) => { if (!r.ok) throw new Error("Could not load inventory"); return r.json() as Promise<Product[]>; }),
        request<Customer[]>("/seller/customers", auth),
        request<OrderSummary[]>("/seller/orders", auth),
      ]);
      const detailed = await Promise.all(summaries.map((row) => request<Order>(`/seller/orders/${row.order_id}`, auth)));
      setProducts(stock); setCustomers(people); setOrders(detailed);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load your workspace"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem("stockroom-token");
    if (!stored) return;
    request<Profile>("/seller/me", stored).then((who) => { setToken(stored); setProfile(who); return refresh(stored, who); }).catch(() => { window.localStorage.removeItem("stockroom-token"); });
  }, [refresh]);

  const activeOrders = useMemo(() => orders.filter((order) => order.status === "confirmed").length, [orders]);
  const totalUnits = useMemo(() => products.reduce((total, item) => total + item.stock, 0), [products]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setLoginBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API}/seller/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: form.get("username"), password: form.get("password") }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Login failed");
      const auth = body.access_token as string;
      const who = await request<Profile>("/seller/me", auth);
      window.localStorage.setItem("stockroom-token", auth); setToken(auth); setProfile(who); setSection("Overview"); await refresh(auth, who);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not sign in"); }
    finally { setLoginBusy(false); }
  }

  function signOut() { window.localStorage.removeItem("stockroom-token"); setToken(""); setProfile(null); setProducts([]); setCustomers([]); setOrders([]); }
  function flash(message: string) { setNotice(message); window.setTimeout(() => setNotice(""), 3200); }

  async function addCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!profile) return;
    const form = new FormData(event.currentTarget);
    try {
      await request<Customer>("/seller/customers", token, { method: "POST", body: JSON.stringify({ name: form.get("name"), phone: form.get("phone") || null, address: form.get("address") || null }) });
      event.currentTarget.reset(); await refresh(token, profile); flash("Customer added");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not add customer"); }
  }

  async function saveInventory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!profile) return;
    const form = new FormData(event.currentTarget);
    const id = String(form.get("id")).trim(); const name = String(form.get("name")).trim();
    const stock = Number(form.get("stock")); const unit_price = Number(form.get("price"));
    const updated = [...products.filter((item) => item.id !== id), { id, name, stock, unit_price }];
    try {
      await request(`/inventories/${profile.inventory_id}/products`, token, { method: "PUT", body: JSON.stringify(updated.map(({ id: productId, name: productName, ...rest }) => ({ id: productId, name: productName, ...rest }))) });
      event.currentTarget.reset(); await refresh(token, profile); flash("Inventory saved");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save inventory"); }
  }

  async function createOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!profile) return;
    const form = new FormData(event.currentTarget);
    const customerId = Number(form.get("customer")); const productId = String(form.get("product")); const quantity = Number(form.get("quantity"));
    try {
      const result = await request<{ order_id: number; rejected: { product_id: string; message: string }[] }>(`/seller/customers/${customerId}/orders`, token, { method: "POST", body: JSON.stringify({ items: [{ product_id: productId, quantity }] }) });
      event.currentTarget.reset(); await refresh(token, profile);
      flash(result.rejected.length ? `Order #${result.order_id} created with some unavailable items` : `Order #${result.order_id} created`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not create order"); }
  }

  async function deliver(orderId: number) {
    if (!profile) return;
    try { await request(`/seller/orders/${orderId}/deliver`, token, { method: "POST" }); await refresh(token, profile); flash(`Order #${orderId} marked delivered`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update order"); }
  }

  if (!token || !profile) return <main className="login-shell"><div className="login-art"><div className="brand"><span className="brand-mark">s</span> stockroom</div><div className="art-copy"><span className="eyebrow">DISTRIBUTOR WORKSPACE</span><h1>Your whole operation,<br />in one place.</h1><p>Keep stock moving, customers close, and orders on track.</p><div className="art-stats"><div><strong>01</strong><span>Inventory</span></div><div><strong>02</strong><span>Customers</span></div><div><strong>03</strong><span>Orders</span></div></div></div><span className="art-note">A clearer way to run your business.</span></div><div className="login-panel"><form className="login-form" onSubmit={login}><span className="eyebrow muted">WELCOME BACK</span><h2>Sign in to your<br />workspace</h2><p className="subtext">Use your distributor account to continue.</p>{error && <div className="alert">{error}</div>}<label>Username<input required name="username" autoComplete="username" placeholder="Your username" /></label><label>Password<input required name="password" type="password" autoComplete="current-password" placeholder="Your password" /></label><button className="primary-button full" disabled={loginBusy}>{loginBusy ? "Signing in…" : "Sign in"}<span>↗</span></button><p className="login-hint">Need an account? Ask your administrator to set one up.</p></form><span className="login-footer">STOCKROOM · DISTRIBUTOR OPERATIONS</span></div></main>;

  const nav: Section[] = ["Overview", "Inventory", "Customers", "Orders"];
  return <main className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">s</span> stockroom</div><div className="workspace-label">WORKSPACE</div><div className="workspace-card"><div className="workspace-icon">{initials(profile.inventory_name)}</div><div className="workspace-text"><strong>{profile.inventory_name}</strong><span>Distributor account</span></div><span className="chevron">⌄</span></div><nav className="side-nav">{nav.map((item, index) => <button key={item} className={`nav-item ${section === item ? "selected" : ""}`} onClick={() => setSection(item)}><span className="nav-icon">{["◫", "▦", "♧", "↗"][index]}</span>{item}{item === "Orders" && activeOrders > 0 && <span className="nav-count">{activeOrders}</span>}</button>)}</nav><div className="sidebar-bottom"><div className="help-card"><div className="help-icon">?</div><strong>Need a hand?</strong><span>Your workspace is ready whenever you are.</span></div><button className="account-button" onClick={signOut}><span className="avatar">{initials(profile.username)}</span><span className="account-name"><strong>{profile.username}</strong><small>Distributor</small></span><span className="signout">↗</span></button></div></aside>
    <section className="main-area"><header className="topbar"><div className="breadcrumbs"><span>Workspace</span><i>/</i><strong>{section}</strong></div><div className="top-actions"><span className="live-dot">●</span><span className="connected">All changes synced</span><button className="top-avatar" title={profile.username}>{initials(profile.username)}</button></div></header><div className="content"><div className="page-heading"><div><span className="eyebrow muted">{section === "Overview" ? "YOUR BUSINESS AT A GLANCE" : `${profile.inventory_name.toUpperCase()} · OPERATIONS`}</span><h1>{section === "Overview" ? <>Good to see you, {profile.username}.</> : section}</h1><p>{section === "Overview" ? "Here’s what’s happening across your distributor workspace today." : section === "Inventory" ? "Keep product availability and pricing up to date." : section === "Customers" ? "Manage the people and businesses you supply." : "Track customer orders from confirmation through delivery."}</p></div>{section === "Overview" && <div className="date-chip"><span>◷</span> Workspace overview</div>}</div>
      {error && <div className="alert page-alert"><span>{error}</span><button onClick={() => setError("")}>×</button></div>}{notice && <div className="toast">✓ &nbsp;{notice}</div>}{loading && <div className="loading-line"><span /> Updating workspace…</div>}
      {section === "Overview" && <><div className="metric-grid"><Metric icon="▦" label="Products in stock" value={products.length.toString()} note={`${totalUnits.toLocaleString()} total units available`} tone="lavender" /><Metric icon="♧" label="Your customers" value={customers.length.toString()} note="Saved customer profiles" tone="peach" /><Metric icon="↗" label="Open orders" value={activeOrders.toString()} note="Confirmed and awaiting delivery" tone="mint" /></div><div className="overview-grid"><div className="panel inventory-panel"><div className="panel-heading"><div><span className="eyebrow muted">STOCK OVERVIEW</span><h3>Inventory snapshot</h3></div><button className="text-button" onClick={() => setSection("Inventory")}>View inventory <span>→</span></button></div>{products.length ? <div className="table-wrap"><table><thead><tr><th>PRODUCT</th><th>UNIT PRICE</th><th>IN STOCK</th><th>STATUS</th></tr></thead><tbody>{products.slice(0, 5).map((item) => <tr key={item.id}><td><div className="product-cell"><span className="product-dot">{initials(item.name)}</span><span><strong>{item.name}</strong><small>{item.id}</small></span></div></td><td>{money(item.unit_price)}</td><td>{item.stock}</td><td><StockStatus count={item.stock} /></td></tr>)}</tbody></table></div> : <Empty text="Your inventory is empty" detail="Add products to start managing stock." action="Add a product" onClick={() => setSection("Inventory")} />}</div><div className="panel activity-panel"><div className="panel-heading"><div><span className="eyebrow muted">LATEST ACTIVITY</span><h3>Recent orders</h3></div><button className="icon-button" onClick={() => setSection("Orders")}>↗</button></div>{orders.slice(0, 5).map((order) => <OrderRow key={order.order_id} order={order} customer={customers.find((person) => person.id === order.directory_customer_id)} />)}{!orders.length && <Empty text="No orders yet" detail="Orders you create will show up here." action="Create an order" onClick={() => setSection("Orders")} />}</div></div></>}
      {section === "Inventory" && <div className="section-grid"><div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">PRODUCT CATALOG</span><h3>Inventory</h3></div><span className="count-pill">{products.length} products</span></div>{products.length ? <div className="table-wrap"><table><thead><tr><th>PRODUCT</th><th>ID</th><th>PRICE</th><th>STOCK</th><th>AVAILABILITY</th></tr></thead><tbody>{products.map((item) => <tr key={item.id}><td><strong>{item.name}</strong></td><td className="mono">{item.id}</td><td>{money(item.unit_price)}</td><td>{item.stock}</td><td><StockStatus count={item.stock} /></td></tr>)}</tbody></table></div> : <Empty text="No products yet" detail="Add your first product using the form." />}</div><form className="panel form-panel" onSubmit={saveInventory}><span className="eyebrow muted">CATALOG UPDATE</span><h3>Add or update a product</h3><p>Entering an existing product ID updates its stock and price.</p><label>Product ID<input name="id" required placeholder="e.g. coffee-250g" /></label><label>Product name<input name="name" required placeholder="e.g. House blend coffee" /></label><div className="field-row"><label>Stock quantity<input name="stock" type="number" min="0" required placeholder="0" /></label><label>Unit price (integer units)<input name="price" type="number" min="0" step="1" required placeholder="0" /></label></div><button className="primary-button">Save product <span>↗</span></button><small className="form-footnote">Prices use the backend’s integer units; currency formatting is not configured yet.</small></form></div>}
      {section === "Customers" && <div className="section-grid"><div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">CUSTOMER DIRECTORY</span><h3>Your customers</h3></div><span className="count-pill">{customers.length} customers</span></div>{customers.length ? <div className="customer-list">{customers.map((person) => <div className="customer-row" key={person.id}><span className="customer-avatar">{initials(person.name)}</span><div className="customer-info"><strong>{person.name}</strong><span>{person.phone || "No phone added"}</span></div><div className="customer-address">{person.address || "—"}</div><span className="customer-id">#{person.id}</span></div>)}</div> : <Empty text="Your customer list is empty" detail="Add a customer to create orders for them." />}</div><form className="panel form-panel" onSubmit={addCustomer}><span className="eyebrow muted">NEW PROFILE</span><h3>Add a customer</h3><p>Save a contact to make placing their orders faster.</p><label>Customer name<input name="name" required maxLength={100} placeholder="Business or contact name" /></label><label>Phone number <span className="optional">OPTIONAL</span><input name="phone" maxLength={30} placeholder="(555) 000-0000" /></label><label>Address <span className="optional">OPTIONAL</span><textarea name="address" maxLength={300} rows={3} placeholder="Street, city, and delivery notes" /></label><button className="primary-button">Save customer <span>↗</span></button></form></div>}
      {section === "Orders" && <div className="section-grid orders-grid"><div className="panel"><div className="panel-heading"><div><span className="eyebrow muted">ORDER ACTIVITY</span><h3>All orders</h3></div><span className="count-pill">{orders.length} total</span></div>{orders.length ? <div className="order-list">{orders.map((order) => <div className="order-card" key={order.order_id}><div className="order-card-top"><div className="order-mark">↗</div><div className="order-main"><strong>Order #{order.order_id}</strong><span>{customers.find((person) => person.id === order.directory_customer_id)?.name || `Customer #${order.directory_customer_id ?? order.customer_id}`}</span></div><StatusBadge status={order.status} /></div><div className="order-items">{order.items.map((item) => <span key={item.product_id}>{item.quantity} × {item.name}</span>)}</div><div className="order-card-bottom"><span>{order.items.length} line items</span><strong>{money(order.total)}</strong>{order.status === "confirmed" && <button className="deliver-button" onClick={() => deliver(order.order_id)}>Mark delivered <span>→</span></button>}</div></div>)}</div> : <Empty text="No orders to show" detail="Create an order for one of your customers." />}</div><form className="panel form-panel" onSubmit={createOrder}><span className="eyebrow muted">NEW ORDER</span><h3>Create an order</h3><p>Choose a customer and add a product from your inventory.</p><label>Customer<select name="customer" required defaultValue=""><option value="" disabled>Select a customer</option>{customers.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label><label>Product<select name="product" required defaultValue=""><option value="" disabled>Select a product</option>{products.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.stock} in stock</option>)}</select></label><label>Quantity<input name="quantity" type="number" min="1" required placeholder="1" /></label><button className="primary-button" disabled={!customers.length || !products.length}>Create order <span>↗</span></button>{(!customers.length || !products.length) && <small className="form-footnote">Add at least one customer and one stocked product first.</small>}</form></div>}
      <footer className="page-footer"><span>STOCKROOM</span><span>Distributor operations, made clearer.</span></footer></div></section></main>;
}

function Metric({ icon, label, value, note, tone }: { icon: string; label: string; value: string; note: string; tone: string }) { return <div className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span><span className="metric-arrow">↗</span></div>; }
function StockStatus({ count }: { count: number }) { return <span className={`stock-status ${count === 0 ? "out" : count < 10 ? "low" : "in"}`}><i />{count === 0 ? "Out of stock" : count < 10 ? "Low stock" : "In stock"}</span>; }
function StatusBadge({ status }: { status: Order["status"] }) { return <span className={`status-badge ${status}`}><i />{status}</span>; }
function OrderRow({ order, customer }: { order: Order; customer?: Customer }) { return <div className="activity-row"><span className="activity-icon">↗</span><div className="activity-copy"><strong>Order #{order.order_id}</strong><span>{customer?.name || `Customer #${order.directory_customer_id ?? order.customer_id}`} · {order.items.length} items</span></div><div className="activity-right"><strong>{money(order.total)}</strong><StatusBadge status={order.status} /></div></div>; }
function Empty({ text, detail, action, onClick }: { text: string; detail: string; action?: string; onClick?: () => void }) { return <div className="empty-state"><span className="empty-icon">⌁</span><strong>{text}</strong><span>{detail}</span>{action && <button className="text-button" onClick={onClick}>{action} →</button>}</div>; }
