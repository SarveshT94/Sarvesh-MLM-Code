import api from "./api";

export const fetchPackages = async () => {
  try {
    const response = await api.get("/packages");
    // 🔥 FIXED: Only return packages where is_active is true!
    const activePackages = (response.data.data || []).filter(pkg => pkg.is_active);
    return { success: true, data: activePackages };
  } catch (error) {
    console.error("Package Fetch Error:", error);
    return { success: false, data: [] };
  }
};

export const purchasePlan = async (planId) => {
  try {
    const response = await api.post("/packages/buy", { plan_id: planId });
    return { success: true, message: response.data.message };
  } catch (error) {
    return { 
      success: false, 
      message: error.response?.data?.message || "Transaction failed." 
    };
  }
};

// 🔥 NEW: Fetch dynamic earning rules from the database
export const fetchCompensationPlan = async () => {
  try {
    const response = await api.get("/compensation-plan");
    return { success: true, data: response.data };
  } catch (error) {
    console.error("Compensation Fetch Error:", error);
    return { success: false, data: null };
  }
};


// ... existing fetchPackages and purchasePlan code ...

// 🔥 NEW: Fetch user's purchase history
export const fetchUserOrders = async () => {
  try {
    const response = await api.get("/user/orders");
    return { success: true, data: response.data.data || [] };
  } catch (error) {
    console.error("Order Fetch Error:", error);
    return { success: false, data: [] };
  }
};
