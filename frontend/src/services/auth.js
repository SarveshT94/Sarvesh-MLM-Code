// src/services/auth.js

import api from "./api";

// 🔐 Login API
export const loginUser = async (data) => {
  try {
    console.log("LOGIN REQUEST DATA:", data); // ✅ debug

    const response = await api.post("/auth/login", data);

    console.log("LOGIN SUCCESS RESPONSE:", response.data); // ✅ debug

    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    console.error("LOGIN ERROR FULL:", error); // ✅ full error
    console.error("LOGIN ERROR RESPONSE:", error.response?.data); // ✅ backend error

    return {
      success: false,
      message:
        error.response?.data?.message ||
        error.message ||
        "Login failed. Try again.",
    };
  }
};

// 🧾 Register API
export const registerUser = async (data) => {
  try {
    console.log("REGISTER REQUEST DATA:", data); // ✅ debug

    const response = await api.post("/auth/register", data);

    console.log("REGISTER SUCCESS:", response.data); // ✅ debug

    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    console.error("REGISTER ERROR:", error.response?.data);

    return {
      success: false,
      message:
        error.response?.data?.message ||
        error.message ||
        "Registration failed.",
    };
  }
};
