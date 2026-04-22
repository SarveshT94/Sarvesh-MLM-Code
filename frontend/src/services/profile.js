import api from "./api";

// 📡 Step 1: Request OTP for Email/Phone change
export const requestProfileUpdate = async (type, newIdentifier) => {
  try {
    const response = await api.post("/profile/request-update", { 
      type, 
      new_identifier: newIdentifier 
    });
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      message: error.response?.data?.message || "Failed to request update." 
    };
  }
};

// 🔐 Step 2: Verify OTP and save
export const verifyProfileOtp = async (otpCode) => {
  try {
    const response = await api.post("/profile/verify-otp", { otp_code: otpCode });
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      message: error.response?.data?.message || "Invalid or expired OTP." 
    };
  }
};
