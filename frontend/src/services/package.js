import api from "./api";

export const fetchPackages = async () => {
  try {
    const response = await api.get("/packages");
    // Only return packages where is_active is true
    const activePackages = (response.data.data || []).filter(pkg => pkg.is_active);
    return { success: true, data: activePackages };
  } catch (error) {
    console.error("Package Fetch Error:", error);
    return { success: false, data: [] };
  }
};

export const fetchCompensationPlan = async () => {
  try {
    const response = await api.get("/compensation-plan");
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Compensation Fetch Error:", error);
    return { success: false, data: null };
  }
};

export const fetchUserOrders = async () => {
  try {
    const response = await api.get("/user/orders");
    return { success: true, data: response.data.data || [] };
  } catch (error) {
    console.error("Order Fetch Error:", error);
    return { success: false, data: [] };
  }
};

// ============================================================================
// 🔥 V2.0 ENTERPRISE UPGRADE: ONLINE PAYMENT GATEWAY INTEGRATION
// ============================================================================

// 1. Dynamic Script Loader (Loads the Razorpay pop-up engine securely)
const loadRazorpayScript = () => {
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
};

// 2. The Secure Checkout Flow
export const purchasePlan = async (pkg, user) => {
  try {
    // Step A: Load the payment window engine
    const isLoaded = await loadRazorpayScript();
    if (!isLoaded) {
      return { success: false, message: "Payment gateway failed to load. Check your connection." };
    }

    // Step B: Ask the Python backend to generate a secure Order ID
    const orderResponse = await api.post("/payment/create-order", { 
      plan_id: pkg.id 
    });

    if (!orderResponse.data.success) {
      return { success: false, message: orderResponse.data.message || "Failed to initialize checkout." };
    }

    const { order_id, key_id, amount } = orderResponse.data;

    // Step C: Open the Payment Modal
    return new Promise((resolve) => {
      const options = {
        key: key_id,
        amount: amount, // Amount is in paise (₹1 = 100 paise)
        currency: "INR",
        name: "RK Trendz",
        description: `Activation for ${pkg.name}`,
        order_id: order_id,
        prefill: {
          name: user.full_name,
          email: user.email,
          contact: user.phone || ""
        },
        theme: {
          color: "#059669" // Matches your Tailwind emerald-600 theme perfectly
        },
        handler: function (response) {
          // Success! Razorpay takes the money, closes the modal, and pings our Python Webhook.
          // We resolve this promise so your Next.js Dashboard shows the green success checkmark.
          resolve({ success: true, message: "Payment successful! Your account is now active." });
        },
      };

      const paymentObject = new window.Razorpay(options);
      
      paymentObject.on("payment.failed", function (response) {
        resolve({ success: false, message: "Payment was cancelled or failed." });
      });
      
      paymentObject.open();
    });

  } catch (error) {
    return { 
      success: false, 
      message: error.response?.data?.message || "Transaction initialization failed." 
    };
  }
};
