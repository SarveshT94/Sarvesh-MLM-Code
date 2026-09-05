"use client";

/*
 * frontend/src/components/store/Storefront.jsx  —  NEW
 * ------------------------------------------------------------------
 * Member storefront (replaces the old "pick a package" catalog tab).
 *
 *   Categories ▸ product grid (search / sort / price) ▸ product page with
 *   variants ▸ cart drawer with the PLAN METER ▸ address ▸ pay
 *   (wallet / Razorpay / split) ▸ order confirmation.
 *
 * The PLAN METER is the MLM hook: it shows how far the cart is from each
 * plan tier and what the current cart will do (activate / upgrade /
 * repurchase). Business rules come from the backend — nothing is hard-coded.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ShoppingCart, Search, ChevronLeft, Plus, Minus, Trash2, MapPin, Wallet,
  CreditCard, CheckCircle2, AlertCircle, Sparkles, Package, Filter, X, Loader2,
} from "lucide-react";
import {
  fetchCategories, fetchProducts, fetchProduct, fetchCart, addToCart, updateCartItem,
  fetchAddresses, saveAddress, deleteAddress, checkout, verifyPayment, openRazorpay,
  imgUrl, inr,
} from "@/services/store";

/* ------------------------------------------------------------------ */
/* small UI bits                                                        */
/* ------------------------------------------------------------------ */
const Img = ({ src, alt, className }) => {
  const [err, setErr] = useState(false);
  const url = imgUrl(src);
  if (!url || err) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 text-slate-300 ${className}`}>
        <Package className="h-10 w-10" />
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={alt || ""} className={className} onError={() => setErr(true)} />;
};

const Toast = ({ toast, onClose }) => {
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [toast, onClose]);
  if (!toast) return null;
  const ok = toast.type !== "error";
  return (
    <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-[80] px-5 py-3 rounded-2xl shadow-2xl text-sm font-bold flex items-center gap-2 ${ok ? "bg-emerald-600 text-white" : "bg-red-600 text-white"}`}>
      {ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
      {toast.message}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* PLAN METER                                                           */
/* ------------------------------------------------------------------ */
const PlanMeter = ({ cart, compact = false }) => {
  const pm = cart?.plan_match;
  if (!pm) return null;
  const subtotal = cart.subtotal || 0;
  const tiers = pm.tiers || [];
  const maxTier = tiers.length ? tiers[tiers.length - 1].price : 1;
  const pct = Math.min(100, (subtotal / maxTier) * 100);

  const headline =
    pm.kind === "activation" ? `🎉 This cart activates the ${pm.plan.name} plan (${inr(pm.plan.price)}) — all plan benefits apply.`
    : pm.kind === "upgrade" ? `⬆️ This cart upgrades you to the ${pm.plan.name} plan (${inr(pm.plan.price)}).`
    : pm.kind === "repurchase" ? "🛒 Repurchase order — repurchase cashback + referral bonus apply, and it counts toward your rank volume."
    : pm.reason;

  return (
    <div className={`rounded-2xl border ${pm.can_checkout ? "border-emerald-200 bg-emerald-50/60" : "border-amber-200 bg-amber-50/60"} ${compact ? "p-3" : "p-4"}`}>
      <div className="flex items-start gap-2">
        <Sparkles className={`h-4 w-4 mt-0.5 ${pm.can_checkout ? "text-emerald-600" : "text-amber-600"}`} />
        <p className="text-xs font-bold text-slate-700 leading-snug">{headline}</p>
      </div>

      {/* tier ruler */}
      <div className="relative mt-4 h-2 rounded-full bg-slate-200">
        <div className="absolute inset-y-0 left-0 rounded-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }} />
        {tiers.map((t) => (
          <div key={t.id} className="absolute -top-1.5" style={{ left: `calc(${Math.min(100, (t.price / maxTier) * 100)}% - 6px)` }} title={`${t.name} ${inr(t.price)}`}>
            <div className={`h-5 w-3 rounded-full border-2 ${t.matched ? "bg-emerald-600 border-emerald-700 scale-125" : t.is_current ? "bg-purple-500 border-purple-600" : subtotal >= t.price ? "bg-emerald-400 border-emerald-500" : "bg-white border-slate-300"}`} />
          </div>
        ))}
      </div>
      <div className="flex justify-between mt-2 text-[10px] font-bold text-slate-500">
        {tiers.map((t) => (
          <span key={t.id} className={t.matched ? "text-emerald-700" : t.is_current ? "text-purple-600" : ""}>{t.name}<br />{inr(t.price)}</span>
        ))}
      </div>

      {!compact && (pm.next_tier || pm.prev_tier) && pm.kind !== "activation" && pm.kind !== "upgrade" && (
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold">
          {pm.next_tier && <span className="px-2 py-1 rounded-lg bg-white border border-slate-200 text-slate-600">Add {inr(pm.next_tier.add_to_reach)} more → <b>{pm.next_tier.name}</b></span>}
          {pm.prev_tier && subtotal > pm.prev_tier.price && <span className="px-2 py-1 rounded-lg bg-white border border-slate-200 text-slate-600">Remove {inr(pm.prev_tier.remove_to_reach)} → <b>{pm.prev_tier.name}</b></span>}
        </div>
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* PRODUCT CARD / GRID                                                  */
/* ------------------------------------------------------------------ */
const ProductCard = ({ p, onOpen }) => {
  const off = p.mrp && p.min_price && p.mrp > p.min_price ? Math.round(((p.mrp - p.min_price) / p.mrp) * 100) : 0;
  return (
    <button onClick={() => onOpen(p)} className="group text-left bg-white rounded-3xl border border-slate-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden hover:shadow-xl hover:-translate-y-0.5 transition-all">
      <div className="relative aspect-square overflow-hidden bg-slate-50">
        <Img src={p.image_url} alt={p.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        {off > 0 && <span className="absolute top-3 left-3 bg-emerald-600 text-white text-[10px] font-black px-2 py-1 rounded-lg">{off}% OFF</span>}
        {!p.in_stock && <span className="absolute inset-0 bg-white/70 flex items-center justify-center text-slate-600 font-black text-sm">Out of stock</span>}
      </div>
      <div className="p-4">
        <p className="text-[10px] font-black uppercase tracking-widest text-slate-400">{p.category_name}{p.brand ? ` · ${p.brand}` : ""}</p>
        <h4 className="font-bold text-slate-900 leading-tight mt-1 line-clamp-2 min-h-[2.5rem]">{p.name}</h4>
        <div className="flex items-baseline gap-2 mt-2">
          <span className="text-lg font-black text-slate-900">{inr(p.min_price)}</span>
          {p.max_price > p.min_price && <span className="text-xs text-slate-400 font-semibold">– {inr(p.max_price)}</span>}
          {p.mrp > p.min_price && <span className="text-xs text-slate-400 line-through">{inr(p.mrp)}</span>}
        </div>
        {p.variant_count > 1 && <p className="text-[11px] text-slate-500 font-semibold mt-1">{p.variant_count} options</p>}
      </div>
    </button>
  );
};

/* ------------------------------------------------------------------ */
/* PRODUCT DETAIL                                                       */
/* ------------------------------------------------------------------ */
const ProductDetail = ({ product, onBack, onAdd, busy }) => {
  const [variantId, setVariantId] = useState(product.variants?.[0]?.id);
  const [qty, setQty] = useState(1);
  const [img, setImg] = useState(0);
  const v = product.variants.find((x) => x.id === variantId) || product.variants[0];
  const images = product.images?.length ? product.images : [{ image_url: null }];

  // group attributes → {size:[..], color:[..]}
  const attrKeys = useMemo(() => {
    const keys = {};
    product.variants.forEach((x) => Object.entries(x.attributes || {}).forEach(([k, val]) => {
      keys[k] = keys[k] || new Set(); keys[k].add(val);
    }));
    return Object.fromEntries(Object.entries(keys).map(([k, s]) => [k, [...s]]));
  }, [product]);

  const pick = (k, val) => {
    const cur = { ...(v.attributes || {}), [k]: val };
    const exact = product.variants.find((x) => Object.entries(cur).every(([kk, vv]) => (x.attributes || {})[kk] === vv));
    const loose = product.variants.find((x) => (x.attributes || {})[k] === val);
    setVariantId((exact || loose || v).id);
  };

  return (
    <div className="animate-in fade-in slide-in-from-right-4 duration-300">
      <button onClick={onBack} className="flex items-center text-sm font-bold text-slate-500 hover:text-emerald-600 mb-4"><ChevronLeft className="h-4 w-4 mr-1" /> Back to {product.category_name}</button>
      <div className="grid md:grid-cols-2 gap-8 bg-white rounded-[2rem] border border-slate-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-6 md:p-8">
        <div>
          <div className="aspect-square rounded-3xl overflow-hidden bg-slate-50 border border-slate-100">
            <Img src={images[img]?.image_url} alt={product.name} className="w-full h-full object-cover" />
          </div>
          {images.length > 1 && (
            <div className="flex gap-2 mt-3 overflow-x-auto">
              {images.map((im, i) => (
                <button key={im.id || i} onClick={() => setImg(i)} className={`h-16 w-16 rounded-xl overflow-hidden border-2 shrink-0 ${i === img ? "border-emerald-500" : "border-transparent"}`}>
                  <Img src={im.image_url} className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>
        <div>
          <p className="text-[11px] font-black uppercase tracking-widest text-emerald-600">{product.category_name}{product.brand ? ` · ${product.brand}` : ""}</p>
          <h2 className="text-2xl md:text-3xl font-black text-slate-900 mt-1 leading-tight">{product.name}</h2>
          <div className="flex items-baseline gap-3 mt-4">
            <span className="text-3xl font-black text-slate-900">{inr(v?.price)}</span>
            {v?.mrp > v?.price && <><span className="text-slate-400 line-through font-semibold">{inr(v.mrp)}</span><span className="text-emerald-600 font-black text-sm">{Math.round(((v.mrp - v.price) / v.mrp) * 100)}% off</span></>}
          </div>
          <p className="text-[11px] text-slate-400 font-semibold mt-1">Inclusive of {product.gst_percent}% GST · SKU {v?.sku}</p>

          {Object.entries(attrKeys).map(([k, vals]) => (
            <div key={k} className="mt-5">
              <p className="text-xs font-black uppercase tracking-wider text-slate-500 mb-2">{k}</p>
              <div className="flex flex-wrap gap-2">
                {vals.map((val) => {
                  const active = (v.attributes || {})[k] === val;
                  const avail = product.variants.some((x) => (x.attributes || {})[k] === val && x.stock_qty > 0);
                  return (
                    <button key={val} onClick={() => pick(k, val)} disabled={!avail}
                      className={`px-4 py-2 rounded-xl text-sm font-bold border transition-all ${active ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"} ${!avail ? "opacity-40 line-through" : ""}`}>
                      {val}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="mt-6 flex items-center gap-4">
            <div className="flex items-center border border-slate-200 rounded-xl overflow-hidden">
              <button onClick={() => setQty(Math.max(1, qty - 1))} className="px-3 py-2 hover:bg-slate-50"><Minus className="h-4 w-4" /></button>
              <span className="px-4 font-black">{qty}</span>
              <button onClick={() => setQty(Math.min(v?.stock_qty || 1, qty + 1))} className="px-3 py-2 hover:bg-slate-50"><Plus className="h-4 w-4" /></button>
            </div>
            <span className={`text-xs font-bold ${v?.stock_qty > 5 ? "text-emerald-600" : v?.stock_qty > 0 ? "text-amber-600" : "text-red-600"}`}>
              {v?.stock_qty > 5 ? "In stock" : v?.stock_qty > 0 ? `Only ${v.stock_qty} left` : "Out of stock"}
            </span>
          </div>

          <button disabled={!v || v.stock_qty <= 0 || busy} onClick={() => onAdd(v.id, qty)}
            className="mt-5 w-full md:w-auto px-8 py-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-black shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 transition-all">
            {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <ShoppingCart className="h-5 w-5" />} Add to cart · {inr((v?.price || 0) * qty)}
          </button>

          {product.highlights_list?.length > 0 && (
            <ul className="mt-6 space-y-1.5">
              {product.highlights_list.map((h, i) => <li key={i} className="flex items-start text-sm text-slate-600"><CheckCircle2 className="h-4 w-4 text-emerald-500 mr-2 mt-0.5 shrink-0" />{h}</li>)}
            </ul>
          )}
          {product.description && <p className="mt-5 text-sm text-slate-600 leading-relaxed whitespace-pre-line">{product.description}</p>}
        </div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* CART + CHECKOUT DRAWER                                               */
/* ------------------------------------------------------------------ */
const AddressForm = ({ onSave, onCancel }) => {
  const [f, setF] = useState({ full_name: "", phone: "", line1: "", line2: "", landmark: "", city: "", state: "", pincode: "", is_default: true });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const inp = "w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500";
  return (
    <div className="space-y-2 bg-slate-50 rounded-2xl p-4 border border-slate-200">
      <div className="grid grid-cols-2 gap-2">
        <input className={inp} placeholder="Full name *" value={f.full_name} onChange={set("full_name")} />
        <input className={inp} placeholder="Mobile *" value={f.phone} onChange={set("phone")} />
      </div>
      <input className={inp} placeholder="House no, street *" value={f.line1} onChange={set("line1")} />
      <input className={inp} placeholder="Area / locality" value={f.line2} onChange={set("line2")} />
      <input className={inp} placeholder="Landmark" value={f.landmark} onChange={set("landmark")} />
      <div className="grid grid-cols-3 gap-2">
        <input className={inp} placeholder="City *" value={f.city} onChange={set("city")} />
        <input className={inp} placeholder="State *" value={f.state} onChange={set("state")} />
        <input className={inp} placeholder="PIN *" value={f.pincode} onChange={set("pincode")} />
      </div>
      <div className="flex gap-2 pt-1">
        <button onClick={() => onSave(f)} className="flex-1 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-black">Save address</button>
        <button onClick={onCancel} className="px-4 py-2.5 rounded-xl bg-white border border-slate-200 text-sm font-bold">Cancel</button>
      </div>
    </div>
  );
};

const CartDrawer = ({ open, onClose, cart, reload, notify, onOrderPlaced }) => {
  const [step, setStep] = useState("cart"); // cart | address | pay
  const [addresses, setAddresses] = useState([]);
  const [addrId, setAddrId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [method, setMethod] = useState("online");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) { setStep("cart"); return; }
    fetchAddresses().then((r) => {
      if (r.success) {
        setAddresses(r.data);
        const d = r.data.find((a) => a.is_default) || r.data[0];
        setAddrId(d?.id || null);
        setShowForm(r.data.length === 0);
      }
    });
  }, [open]);

  const items = cart?.items || [];
  const pm = cart?.plan_match;
  const wallet = cart?.wallet_balance || 0;
  const total = cart?.total || 0;
  const walletCovers = wallet >= total;

  useEffect(() => { if (!walletCovers && method === "wallet") setMethod(wallet > 0 ? "split" : "online"); }, [walletCovers, wallet, method]);

  const changeQty = async (variant_id, qty) => {
    const r = await updateCartItem(variant_id, qty);
    if (!r.success) notify(r.message, "error");
    reload();
  };

  const onSaveAddress = async (f) => {
    const r = await saveAddress(f);
    if (!r.success) return notify(r.message, "error");
    setAddresses(r.data); setAddrId(r.id); setShowForm(false);
  };

  const pay = async () => {
    if (!addrId) return notify("Please add a delivery address", "error");
    setBusy(true);
    const r = await checkout({ address_id: addrId, payment_method: method });
    if (!r.success) { setBusy(false); return notify(r.message, "error"); }
    const { order, payment } = r;
    if (payment.online_due > 0 && payment.gateway) {
      const gw = payment.gateway;
      if (!gw.key_id) {
        setBusy(false);
        notify("Online payment is not configured yet. Your order is saved as awaiting payment — the admin can confirm it manually.", "error");
        reload(); onOrderPlaced(order); onClose();
        return;
      }
      const res = await openRazorpay(gw, async (resp) => {
        return verifyPayment({
          gateway_order_id: gw.gateway_order_id,
          gateway_payment_id: resp.razorpay_payment_id,
          signature: resp.razorpay_signature,
        });
      });
      setBusy(false);
      if (res.success) { notify("Payment successful! Order confirmed."); reload(); onOrderPlaced(order); onClose(); }
      else if (res.dismissed) { notify("Payment not completed. Your order is saved under My Orders — you can pay again later.", "error"); reload(); onOrderPlaced(order); onClose(); }
      else notify(res.message || "Payment verification failed", "error");
      return;
    }
    setBusy(false);
    notify(`Order ${order.order_no} placed & paid from wallet!`);
    reload(); onOrderPlaced(order); onClose();
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[70] flex justify-end">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-lg font-black text-slate-900 flex items-center gap-2"><ShoppingCart className="h-5 w-5 text-emerald-600" />
            {step === "cart" ? `Your cart (${cart?.item_count || 0})` : step === "address" ? "Delivery address" : "Payment"}</h3>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {step === "cart" && (
            <>
              {items.length === 0 && <div className="text-center py-16 text-slate-400"><ShoppingCart className="h-12 w-12 mx-auto mb-3 opacity-40" /><p className="font-bold">Your cart is empty</p></div>}
              {items.map((it) => (
                <div key={it.item_id} className="flex gap-3 items-center">
                  <Img src={it.image_url} className="h-16 w-16 rounded-xl object-cover border border-slate-100 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-bold text-sm text-slate-900 truncate">{it.product_name}</p>
                    <p className="text-[11px] text-slate-500 font-semibold">{it.label} · {inr(it.price)}</p>
                    {!it.stock_ok && <p className="text-[11px] text-red-600 font-bold">Only {it.stock_qty} available</p>}
                    <div className="flex items-center gap-2 mt-1">
                      <button onClick={() => changeQty(it.variant_id, it.qty - 1)} className="h-7 w-7 rounded-lg border border-slate-200 flex items-center justify-center hover:bg-slate-50"><Minus className="h-3 w-3" /></button>
                      <span className="text-sm font-black w-5 text-center">{it.qty}</span>
                      <button onClick={() => changeQty(it.variant_id, it.qty + 1)} className="h-7 w-7 rounded-lg border border-slate-200 flex items-center justify-center hover:bg-slate-50"><Plus className="h-3 w-3" /></button>
                      <button onClick={() => changeQty(it.variant_id, 0)} className="ml-auto text-slate-400 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                    </div>
                  </div>
                  <p className="font-black text-sm text-slate-900">{inr(it.line_total)}</p>
                </div>
              ))}
              {items.length > 0 && <PlanMeter cart={cart} />}
            </>
          )}

          {step === "address" && (
            <>
              {addresses.map((a) => (
                <button key={a.id} onClick={() => setAddrId(a.id)} className={`w-full text-left p-4 rounded-2xl border-2 transition-all ${addrId === a.id ? "border-emerald-500 bg-emerald-50/50" : "border-slate-200 hover:border-slate-300"}`}>
                  <div className="flex items-start gap-2"><MapPin className={`h-4 w-4 mt-0.5 ${addrId === a.id ? "text-emerald-600" : "text-slate-400"}`} />
                    <div className="flex-1"><p className="font-black text-sm text-slate-900">{a.full_name} <span className="text-slate-400 font-semibold">· {a.phone}</span></p>
                      <p className="text-xs text-slate-600 mt-0.5">{a.line1}{a.line2 ? `, ${a.line2}` : ""}{a.landmark ? `, near ${a.landmark}` : ""}<br />{a.city}, {a.state} – {a.pincode}</p></div>
                    <button onClick={async (e) => { e.stopPropagation(); const r = await deleteAddress(a.id); if (r.success) { setAddresses(r.data); if (addrId === a.id) setAddrId(r.data[0]?.id || null); } }} className="text-slate-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                  </div>
                </button>
              ))}
              {showForm ? <AddressForm onSave={onSaveAddress} onCancel={() => setShowForm(false)} />
                : <button onClick={() => setShowForm(true)} className="w-full py-3 rounded-2xl border-2 border-dashed border-slate-300 text-sm font-bold text-slate-500 hover:border-emerald-400 hover:text-emerald-600">+ Add new address</button>}
            </>
          )}

          {step === "pay" && (
            <>
              <PlanMeter cart={cart} compact />
              <div className="space-y-2">
                {[
                  { id: "wallet", label: "Pay from earnings wallet", sub: `Balance ${inr(wallet)}`, icon: Wallet, disabled: !walletCovers },
                  { id: "split", label: "Wallet + Online", sub: `${inr(Math.min(wallet, total))} from wallet, ${inr(Math.max(0, total - wallet))} online`, icon: Sparkles, disabled: wallet <= 0 || walletCovers },
                  { id: "online", label: "Pay online", sub: "UPI · Cards · Net banking (Razorpay)", icon: CreditCard, disabled: false },
                ].map((m) => (
                  <button key={m.id} disabled={m.disabled} onClick={() => setMethod(m.id)} className={`w-full text-left p-4 rounded-2xl border-2 flex items-center gap-3 transition-all disabled:opacity-40 ${method === m.id ? "border-emerald-500 bg-emerald-50/50" : "border-slate-200 hover:border-slate-300"}`}>
                    <m.icon className={`h-5 w-5 ${method === m.id ? "text-emerald-600" : "text-slate-400"}`} />
                    <div><p className="font-black text-sm text-slate-900">{m.label}</p><p className="text-[11px] text-slate-500 font-semibold">{m.sub}</p></div>
                  </button>
                ))}
              </div>
              <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4 text-sm space-y-1.5">
                <div className="flex justify-between text-slate-600"><span>Items ({cart.item_count})</span><span className="font-bold">{inr(cart.subtotal)}</span></div>
                <div className="flex justify-between text-slate-400 text-xs"><span>Includes GST</span><span>{inr(cart.gst_included)}</span></div>
                <div className="flex justify-between text-slate-600"><span>Shipping</span><span className="font-bold">{cart.shipping_fee > 0 ? inr(cart.shipping_fee) : "FREE"}</span></div>
                <div className="flex justify-between text-slate-900 text-base font-black border-t border-slate-200 pt-2"><span>Total</span><span>{inr(total)}</span></div>
              </div>
            </>
          )}
        </div>

        {items.length > 0 && (
          <div className="p-5 border-t border-slate-100 bg-white">
            <div className="flex justify-between items-baseline mb-3"><span className="text-sm font-bold text-slate-500">Total</span><span className="text-2xl font-black text-slate-900">{inr(total)}</span></div>
            {step === "cart" && (
              <button disabled={!pm?.can_checkout || !cart.all_available} onClick={() => setStep("address")} className="w-full py-4 rounded-2xl bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white font-black transition-all">
                {pm?.can_checkout ? "Continue to delivery →" : "Adjust cart to a plan amount"}
              </button>
            )}
            {step === "address" && (
              <div className="flex gap-2">
                <button onClick={() => setStep("cart")} className="px-4 py-4 rounded-2xl bg-slate-100 font-black"><ChevronLeft className="h-5 w-5" /></button>
                <button disabled={!addrId} onClick={() => setStep("pay")} className="flex-1 py-4 rounded-2xl bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white font-black">Continue to payment →</button>
              </div>
            )}
            {step === "pay" && (
              <div className="flex gap-2">
                <button onClick={() => setStep("address")} className="px-4 py-4 rounded-2xl bg-slate-100 font-black"><ChevronLeft className="h-5 w-5" /></button>
                <button disabled={busy} onClick={pay} className="flex-1 py-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-black flex items-center justify-center gap-2">
                  {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />} {method === "wallet" ? `Pay ${inr(total)} from wallet` : `Pay ${inr(method === "split" ? Math.max(0, total - wallet) : total)} online`}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* MAIN                                                                 */
/* ------------------------------------------------------------------ */
export default function Storefront({ onOrderPlaced }) {
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], pages: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const [product, setProduct] = useState(null);
  const [cart, setCart] = useState(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);
  const notify = useCallback((message, type = "ok") => setToast({ message, type, id: Date.now() }), []);

  const reloadCart = useCallback(async () => { const r = await fetchCart(); if (r.success) setCart(r.data); }, []);

  useEffect(() => { fetchCategories().then((r) => r.success && setCategories(r.data)); reloadCart(); }, [reloadCart]);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      fetchProducts({ category, q, sort, page, page_size: 24 }).then((r) => { if (r.success) setData(r); setLoading(false); });
    }, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [category, q, sort, page]);

  const openProduct = async (p) => {
    const r = await fetchProduct(p.slug || p.id);
    if (r.success) { setProduct(r.data); window.scrollTo({ top: 0, behavior: "smooth" }); }
  };

  const onAdd = async (variant_id, qty) => {
    setBusy(true);
    const r = await addToCart(variant_id, qty);
    setBusy(false);
    if (!r.success) return notify(r.message, "error");
    setCart(r.data);
    const pm = r.data.plan_match;
    notify(pm.kind === "activation" || pm.kind === "upgrade" ? `Added! Cart now matches the ${pm.plan.name} plan 🎉` : pm.next_tier ? `Added! Add ${inr(pm.next_tier.add_to_reach)} more for ${pm.next_tier.name}` : "Added to cart");
    setCartOpen(true);
  };

  const pm = cart?.plan_match;

  return (
    <div className="max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
      <Toast toast={toast} onClose={() => setToast(null)} />

      {/* header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-slate-900 tracking-tight">Shop</h2>
          <p className="text-slate-500 font-medium mt-1">Build a cart worth a plan amount to activate or upgrade your plan — every later purchase earns repurchase rewards.</p>
        </div>
        <button onClick={() => setCartOpen(true)} className="relative flex items-center gap-2 px-5 py-3 rounded-2xl bg-slate-900 text-white font-black shadow-lg hover:bg-slate-800 transition-all self-start md:self-auto">
          <ShoppingCart className="h-5 w-5" /> Cart · {inr(cart?.subtotal || 0)}
          {cart?.item_count > 0 && <span className="absolute -top-2 -right-2 h-6 min-w-6 px-1.5 rounded-full bg-emerald-500 text-white text-xs font-black flex items-center justify-center">{cart.item_count}</span>}
        </button>
      </div>

      {/* plan strip */}
      {cart && (cart.item_count > 0 || !pm?.is_active_member) && (
        <div className="mb-6"><PlanMeter cart={cart} /></div>
      )}

      {product ? (
        <ProductDetail product={product} onBack={() => setProduct(null)} onAdd={onAdd} busy={busy} />
      ) : (
        <>
          {/* categories */}
          <div className="flex gap-2 overflow-x-auto pb-2 mb-4 -mx-1 px-1">
            <button onClick={() => { setCategory(""); setPage(1); }} className={`shrink-0 px-5 py-2.5 rounded-2xl text-sm font-black border transition-all ${!category ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-slate-700 border-slate-200 hover:border-emerald-300"}`}>All products</button>
            {categories.map((c) => (
              <button key={c.id} onClick={() => { setCategory(c.slug); setPage(1); }} className={`shrink-0 px-5 py-2.5 rounded-2xl text-sm font-black border transition-all ${category === c.slug ? "bg-emerald-600 text-white border-emerald-600" : "bg-white text-slate-700 border-slate-200 hover:border-emerald-300"}`}>
                {c.name} <span className="opacity-60 font-bold">({c.product_count})</span>
              </button>
            ))}
          </div>

          {/* toolbar */}
          <div className="flex flex-col sm:flex-row gap-3 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search products, brands…" className="w-full pl-11 pr-4 py-3 rounded-2xl border border-slate-200 bg-white font-semibold text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
            </div>
            <div className="relative">
              <Filter className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <select value={sort} onChange={(e) => setSort(e.target.value)} className="pl-11 pr-8 py-3 rounded-2xl border border-slate-200 bg-white font-bold text-sm focus:outline-none">
                <option value="newest">Newest</option><option value="price_asc">Price: low → high</option><option value="price_desc">Price: high → low</option><option value="name">Name A–Z</option>
              </select>
            </div>
          </div>

          {/* grid */}
          {loading ? (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="aspect-[3/4] rounded-3xl bg-slate-100 animate-pulse" />)}</div>
          ) : data.items.length === 0 ? (
            <div className="text-center py-20 bg-white rounded-3xl border border-slate-100"><Package className="h-12 w-12 text-slate-300 mx-auto mb-3" /><p className="font-black text-slate-700">No products found</p><p className="text-sm text-slate-400">Try another category or search term.</p></div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">{data.items.map((p) => <ProductCard key={p.id} p={p} onOpen={openProduct} />)}</div>
          )}

          {data.pages > 1 && (
            <div className="flex justify-center items-center gap-2 mt-8">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-4 py-2 rounded-xl border border-slate-200 bg-white font-bold text-sm disabled:opacity-40">‹ Prev</button>
              <span className="text-sm font-bold text-slate-500">Page {page} / {data.pages}</span>
              <button disabled={page >= data.pages} onClick={() => setPage(page + 1)} className="px-4 py-2 rounded-xl border border-slate-200 bg-white font-bold text-sm disabled:opacity-40">Next ›</button>
            </div>
          )}
        </>
      )}

      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} cart={cart} reload={reloadCart} notify={notify}
        onOrderPlaced={(o) => { setProduct(null); onOrderPlaced && onOrderPlaced(o); }} />
    </div>
  );
}
