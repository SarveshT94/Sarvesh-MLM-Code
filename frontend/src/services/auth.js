import api from "./api";

// 🔐 Login API
export const loginUser = async (data) => {
  try {
    const response = await api.post("/auth/login", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("LOGIN ERROR:", error.response?.data);
    return {
      success: false,
      message: error.response?.data?.message || "Login failed. Please check your credentials.",
    };
  }
};

// 🧾 Register API
export const registerUser = async (data) => {
  try {
    const response = await api.post("/auth/register", data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("REGISTER ERROR:", error.response?.data);
    return {
      success: false,
      message: error.response?.data?.message || "Registration failed.",
    };
  }
};

// 🚪 Logout API (Crucial for destroying the backend cookie)
export const logoutUser = async () => {
  try {
    await api.post("/auth/logout");
    return { success: true };
  } catch (error) {
    console.error("LOGOUT ERROR:", error);
    return { success: false };
  }
};

// 🕵️ Session Verification (Checks if the HttpOnly cookie is still alive)
export const checkAuthSession = async () => {
  try {
    const response = await api.get("/auth/me");
    return { success: true, data: response.data };
  } catch (error) {
    // If this fails, it means the cookie expired or is missing
    return { success: false };
  }
};

// 🔑 Forgot Password API (Upgraded for Email or Phone)
export const forgotPassword = async (identifier) => {
  try {
    // 🔥 FIXED: Now uses 'api' instead of 'axiosInstance', and passes 'identifier'
    const response = await api.post("/auth/forgot-password", { identifier });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      message: error.response?.data?.message || "Failed to send reset link.",
    };
  }
};

// 🔑 Reset Password API
export const resetPassword = async (token, password) => {
  try {
    // 🔥 FIXED: Now uses 'api' instead of 'axiosInstance'
    const response = await api.post("/auth/reset-password", { token, password });
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      message: error.response?.data?.message || "Password reset failed.",
    };
  }
};
