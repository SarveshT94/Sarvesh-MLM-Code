import api from "./api";

/*
 * frontend/src/services/store.js — E-commerce store API client (NEW)
 * All calls go through the shared axios instance (session cookie auth).
 * Every function returns { success, ...payload } and never throws.
 */
const wrap = async (fn) => {
  try {
    const res = await fn();
    return { success: true, ...res.data };
  } catch (error) {
    return {
      success: false,
      message: error.response?.data?.message || "Something went wrong. Please try again.",
      status: error.response?.status,
    };
  }
};

export const fetchCategories = () => wrap(() => api.get("/store/categories"));
export const fetchProducts = (params = {}) => wrap(() => api.get("/store/products", { params }));
export const fetchProduct = (key) => wrap(() => api.get(`/store/products/${key}`));
export const fetchPlanTiers = () => wrap(() => api.get("/store/plans"));

export const fetchCart = () => wrap(() => api.get("/store/cart"));
export const addToCart = (variant_id, qty = 1) => wrap(() => api.post("/store/cart/add", { variant_id, qty }));
export const updateCartItem = (variant_id, qty) => wrap(() => api.post("/store/cart/update", { variant_id, qty }));
export const clearCart = () => wrap(() => api.post("/store/cart/clear"));

export const fetchAddresses = () => wrap(() => api.get("/store/addresses"));
export const saveAddress = (data) => wrap(() => api.post("/store/addresses", data));
export const deleteAddress = (id) => wrap(() => api.post(`/store/addresses/${id}/delete`));

export const checkout = (payload) => wrap(() => api.post("/store/checkout", payload));
export const verifyPayment = (payload) => wrap(() => api.post("/store/payment/verify", payload));

export const fetchMyOrders = (page = 1) => wrap(() => api.get("/store/orders", { params: { page } }));
export const fetchMyOrder = (id) => wrap(() => api.get(`/store/orders/${id}`));
export const cancelMyOrder = (id, reason) => wrap(() => api.post(`/store/orders/${id}/cancel`, { reason }));

/** Absolute URL for product images served by the Flask backend. */
export const imgUrl = (path) => {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  const base = (api.defaults.baseURL || "").replace(/\/api\/?$/, "");
  return `${base}${path}`;
};

export const inr = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

/** Loads Razorpay checkout.js once and opens the payment sheet. */
export const openRazorpay = (gateway, onSuccess, onDismiss) =>
  new Promise((resolve) => {
    const launch = () => {
      if (!window.Razorpay) {
        resolve({ success: false, message: "Payment library failed to load. Check your internet connection." });
        return;
      }
      const rzp = new window.Razorpay({
        key: gateway.key_id,
        amount: gateway.amount_paise,
        currency: gateway.currency || "INR",
        name: gateway.name || "RK Trendz",
        description: "Store purchase",
        notes: { gateway_order_id: gateway.gateway_order_id },
        prefill: gateway.prefill || {},
        theme: { color: "#059669" },
        handler: async (resp) => {
          const r = await onSuccess(resp);
          resolve(r);
        },
        modal: { ondismiss: () => { onDismiss && onDismiss(); resolve({ success: false, dismissed: true }); } },
      });
      rzp.open();
    };
    if (window.Razorpay) return launch();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = launch;
    s.onerror = () => resolve({ success: false, message: "Could not load payment gateway." });
    document.body.appendChild(s);
  });
