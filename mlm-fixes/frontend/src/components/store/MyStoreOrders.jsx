"use client";

/*
 * frontend/src/components/store/MyStoreOrders.jsx  —  NEW
 * ------------------------------------------------------------------
 * Member order history for STORE orders: status tracker
 * (Placed → Confirmed → Packed → Shipped → Delivered), courier/tracking,
 * items, payment split, cancel (before packing) and a printable GST invoice.
 */

import { useCallback, useEffect, useState } from "react";
import { Package, Truck, CheckCircle2, XCircle, Printer, ChevronDown, ChevronUp, Loader2, RefreshCw } from "lucide-react";
import { fetchMyOrders, fetchMyOrder, cancelMyOrder, imgUrl, inr } from "@/services/store";

const FLOW = ["placed", "confirmed", "packed", "shipped", "delivered"];

const KindBadge = ({ kind, plan }) => {
  const cls = kind === "activation" ? "bg-emerald-100 text-emerald-700" : kind === "upgrade" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600";
  return <span className={`px-2 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider ${cls}`}>{kind}{plan ? ` · ${plan}` : ""}</span>;
};

const Tracker = ({ status }) => {
  if (status === "cancelled") return <div className="flex items-center gap-2 text-red-600 font-black text-sm"><XCircle className="h-4 w-4" /> Cancelled</div>;
  const idx = FLOW.indexOf(status);
  return (
    <div className="flex items-center">
      {FLOW.map((s, i) => (
        <div key={s} className="flex items-center flex-1 last:flex-none">
          <div className="flex flex-col items-center">
            <div className={`h-7 w-7 rounded-full flex items-center justify-center border-2 ${i < idx ? "bg-emerald-500 border-emerald-500 text-white" : i === idx ? "bg-slate-900 border-slate-900 text-white" : "bg-white border-slate-200 text-slate-300"}`}>
              {i < idx ? <CheckCircle2 className="h-4 w-4" /> : i === 3 ? <Truck className="h-3.5 w-3.5" /> : <Package className="h-3.5 w-3.5" />}
            </div>
            <span className={`text-[9px] font-black uppercase mt-1 ${i <= idx ? "text-slate-800" : "text-slate-300"}`}>{s}</span>
          </div>
          {i < FLOW.length - 1 && <div className={`h-0.5 flex-1 mx-1 mb-4 ${i < idx ? "bg-emerald-500" : "bg-slate-200"}`} />}
        </div>
      ))}
    </div>
  );
};

const Invoice = ({ o, company, onClose }) => (
  <div className="fixed inset-0 z-[90] bg-white overflow-auto p-8 print:p-0">
    <div className="max-w-3xl mx-auto">
      <div className="flex justify-between items-start border-b-2 border-slate-900 pb-4 mb-6">
        <div><h1 className="text-2xl font-black">{company?.company_name || "RK Trendz"}</h1>
          <p className="text-xs text-slate-500 whitespace-pre-line">{company?.head_office_address}</p>
          {company?.gst_number && <p className="text-xs font-bold mt-1">GSTIN: {company.gst_number}</p>}</div>
        <div className="text-right"><p className="text-xs font-black uppercase tracking-widest text-slate-400">Tax Invoice</p>
          <p className="font-black">{o.order_no}</p><p className="text-xs text-slate-500">{new Date(o.paid_at || o.created_at).toLocaleDateString("en-IN", { dateStyle: "long" })}</p></div>
      </div>
      <div className="grid grid-cols-2 gap-6 text-sm mb-6">
        <div><p className="text-[10px] font-black uppercase text-slate-400">Bill to</p><p className="font-bold">{o.full_name}</p><p className="text-slate-500">{o.email}<br />{o.phone}</p></div>
        <div><p className="text-[10px] font-black uppercase text-slate-400">Ship to</p><p className="font-bold">{o.shipping_address?.full_name}</p>
          <p className="text-slate-500">{o.shipping_address?.line1}{o.shipping_address?.line2 ? `, ${o.shipping_address.line2}` : ""}<br />{o.shipping_address?.city}, {o.shipping_address?.state} – {o.shipping_address?.pincode}</p></div>
      </div>
      <table className="w-full text-sm mb-6">
        <thead><tr className="border-b border-slate-300 text-left text-[10px] uppercase text-slate-500"><th className="py-2">Item</th><th>SKU</th><th className="text-center">Qty</th><th className="text-right">Rate</th><th className="text-right">GST</th><th className="text-right">Amount</th></tr></thead>
        <tbody>{o.items.map((it) => (
          <tr key={it.id} className="border-b border-slate-100"><td className="py-2 font-semibold">{it.product_name}<div className="text-xs text-slate-400">{it.variant_label}</div></td><td className="text-xs text-slate-500">{it.sku}</td><td className="text-center">{it.qty}</td><td className="text-right">{inr(it.unit_price)}</td><td className="text-right">{it.gst_percent}%</td><td className="text-right font-bold">{inr(it.line_total)}</td></tr>
        ))}</tbody>
      </table>
      <div className="flex justify-end"><div className="w-64 text-sm space-y-1">
        <div className="flex justify-between text-slate-500"><span>Subtotal</span><span>{inr(o.subtotal)}</span></div>
        <div className="flex justify-between text-slate-400 text-xs"><span>GST included</span><span>{inr(o.gst_amount)}</span></div>
        <div className="flex justify-between text-slate-500"><span>Shipping</span><span>{inr(o.shipping_fee)}</span></div>
        <div className="flex justify-between font-black text-base border-t border-slate-900 pt-1"><span>Total</span><span>{inr(o.total)}</span></div>
        <div className="flex justify-between text-xs text-slate-400"><span>Paid: wallet {inr(o.wallet_paid)} · online {inr(o.online_paid)}</span></div>
      </div></div>
      <p className="text-[10px] text-slate-400 mt-10">Computer generated invoice · {company?.support_email || ""} {company?.support_phone || ""}</p>
      <div className="print:hidden flex gap-2 mt-8"><button onClick={() => window.print()} className="px-5 py-2.5 rounded-xl bg-slate-900 text-white font-black text-sm flex items-center gap-2"><Printer className="h-4 w-4" /> Print / Save PDF</button><button onClick={onClose} className="px-5 py-2.5 rounded-xl bg-slate-100 font-bold text-sm">Close</button></div>
    </div>
  </div>
);

export default function MyStoreOrders({ company }) {
  const [data, setData] = useState({ items: [], pages: 1 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);
  const [detail, setDetail] = useState({});
  const [invoice, setInvoice] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => { setLoading(true); const r = await fetchMyOrders(page); if (r.success) setData(r); setLoading(false); }, [page]);
  useEffect(() => { load(); }, [load]);

  const toggle = async (id) => {
    if (openId === id) return setOpenId(null);
    setOpenId(id);
    if (!detail[id]) { const r = await fetchMyOrder(id); if (r.success) setDetail((d) => ({ ...d, [id]: r.data })); }
  };

  const cancel = async (id) => {
    if (!confirm("Cancel this order? Paid amounts are refunded to your wallet.")) return;
    setBusy(true);
    const r = await cancelMyOrder(id, "Cancelled by member");
    setBusy(false);
    if (!r.success) return alert(r.message);
    setDetail((d) => ({ ...d, [id]: undefined })); load();
  };

  return (
    <div className="max-w-5xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      {invoice && <Invoice o={invoice} company={company} onClose={() => setInvoice(null)} />}
      <div className="mb-6 flex justify-between items-end">
        <div><h2 className="text-3xl font-black text-slate-900 tracking-tight">My Orders</h2><p className="text-slate-500 font-medium mt-1">Track deliveries and download GST invoices.</p></div>
        <button onClick={load} className="p-3 rounded-xl bg-white border border-slate-200 text-slate-500 hover:text-emerald-600"><RefreshCw className="h-4 w-4" /></button>
      </div>

      {loading ? <div className="flex justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-emerald-600" /></div>
        : data.items.length === 0 ? <div className="text-center py-20 bg-white rounded-3xl border border-slate-100"><Package className="h-12 w-12 text-slate-300 mx-auto mb-3" /><p className="font-black text-slate-700">No orders yet</p><p className="text-sm text-slate-400">Your store purchases will appear here.</p></div>
        : (
          <div className="space-y-4">
            {data.items.map((o) => {
              const d = detail[o.id];
              const open = openId === o.id;
              return (
                <div key={o.id} className="bg-white rounded-3xl border border-slate-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden">
                  <button onClick={() => toggle(o.id)} className="w-full text-left p-5 flex flex-col md:flex-row md:items-center gap-4">
                    <div className="h-16 w-16 rounded-2xl overflow-hidden bg-slate-50 border border-slate-100 shrink-0">
                      {o.image_url ? <img src={imgUrl(o.image_url)} alt="" className="h-full w-full object-cover" /> : <Package className="h-8 w-8 m-4 text-slate-300" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2"><p className="font-black text-slate-900">{o.order_no}</p><KindBadge kind={o.order_kind} plan={o.plan_name} />
                        {o.payment_status !== "paid" && <span className={`px-2 py-1 rounded-lg text-[10px] font-black uppercase ${o.payment_status === "pending" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>{o.payment_status === "pending" ? "Awaiting payment" : o.payment_status}</span>}</div>
                      <p className="text-xs text-slate-500 font-semibold mt-0.5 truncate">{o.first_item}{o.item_count > 1 ? ` + ${o.item_count - 1} more` : ""} · {new Date(o.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</p>
                    </div>
                    <div className="md:w-72"><Tracker status={o.order_status} /></div>
                    <div className="flex items-center gap-3 md:ml-2"><p className="text-lg font-black text-slate-900">{inr(o.total)}</p>{open ? <ChevronUp className="h-5 w-5 text-slate-400" /> : <ChevronDown className="h-5 w-5 text-slate-400" />}</div>
                  </button>

                  {open && (
                    <div className="border-t border-slate-100 p-5 bg-slate-50/50">
                      {!d ? <div className="flex justify-center py-6"><Loader2 className="h-6 w-6 animate-spin text-emerald-600" /></div> : (
                        <div className="grid md:grid-cols-3 gap-6">
                          <div className="md:col-span-2 space-y-3">
                            {d.items.map((it) => (
                              <div key={it.id} className="flex items-center gap-3 bg-white rounded-2xl p-3 border border-slate-100">
                                <div className="h-14 w-14 rounded-xl overflow-hidden bg-slate-50 shrink-0">{it.image_url ? <img src={imgUrl(it.image_url)} alt="" className="h-full w-full object-cover" /> : <Package className="h-6 w-6 m-4 text-slate-300" />}</div>
                                <div className="flex-1 min-w-0"><p className="font-bold text-sm text-slate-900 truncate">{it.product_name}</p><p className="text-[11px] text-slate-500 font-semibold">{it.variant_label} · Qty {it.qty} · {inr(it.unit_price)}</p></div>
                                <p className="font-black text-sm">{inr(it.line_total)}</p>
                              </div>
                            ))}
                            {d.tracking_no && <div className="bg-white rounded-2xl p-4 border border-slate-100 flex items-center gap-3"><Truck className="h-5 w-5 text-emerald-600" /><div><p className="text-xs font-black uppercase text-slate-400">Shipped via {d.courier}</p><p className="font-bold text-slate-900">{d.tracking_no}</p></div></div>}
                            <div className="text-xs text-slate-500 space-y-1 px-1">
                              {d.events.map((e, i) => <p key={i}><span className="font-black text-slate-700 capitalize">{e.status.replace("_", " ")}</span> · {new Date(e.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}{e.note ? ` — ${e.note}` : ""}</p>)}
                            </div>
                          </div>
                          <div className="space-y-3">
                            <div className="bg-white rounded-2xl p-4 border border-slate-100 text-sm space-y-1">
                              <div className="flex justify-between text-slate-500"><span>Items</span><span className="font-bold">{inr(d.subtotal)}</span></div>
                              <div className="flex justify-between text-slate-500"><span>Shipping</span><span className="font-bold">{d.shipping_fee > 0 ? inr(d.shipping_fee) : "FREE"}</span></div>
                              <div className="flex justify-between font-black text-slate-900 border-t border-slate-100 pt-1"><span>Total</span><span>{inr(d.total)}</span></div>
                              <p className="text-[11px] text-slate-400 pt-1">Wallet {inr(d.wallet_paid)} · Online {inr(d.online_paid)}</p>
                            </div>
                            <div className="bg-white rounded-2xl p-4 border border-slate-100 text-xs text-slate-600">
                              <p className="text-[10px] font-black uppercase text-slate-400 mb-1">Delivering to</p>
                              <p className="font-bold text-slate-900">{d.shipping_address?.full_name}</p>
                              <p>{d.shipping_address?.line1}{d.shipping_address?.line2 ? `, ${d.shipping_address.line2}` : ""}<br />{d.shipping_address?.city}, {d.shipping_address?.state} – {d.shipping_address?.pincode}</p>
                            </div>
                            {d.payment_status === "paid" && <button onClick={() => setInvoice(d)} className="w-full py-3 rounded-2xl bg-slate-900 text-white font-black text-sm flex items-center justify-center gap-2"><Printer className="h-4 w-4" /> GST Invoice</button>}
                            {["placed", "confirmed"].includes(d.order_status) && <button disabled={busy} onClick={() => cancel(d.id)} className="w-full py-3 rounded-2xl bg-white border border-red-200 text-red-600 font-black text-sm">Cancel order</button>}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {data.pages > 1 && (
              <div className="flex justify-center items-center gap-2 pt-2">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-4 py-2 rounded-xl border border-slate-200 bg-white font-bold text-sm disabled:opacity-40">‹ Prev</button>
                <span className="text-sm font-bold text-slate-500">Page {page} / {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)} className="px-4 py-2 rounded-xl border border-slate-200 bg-white font-bold text-sm disabled:opacity-40">Next ›</button>
              </div>
            )}
          </div>
        )}
    </div>
  );
}
