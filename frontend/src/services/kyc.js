import api from "./api";

export const fetchKycData = async () => {
  try {
    const response = await api.get("/user/kyc");
    return { success: true, data: response.data.data || null };
  } catch (error) {
    console.error("KYC Fetch Error:", error);
    return { success: false, data: null };
  }
};

export const submitKycData = async (kycDetails) => {
  try {
    const response = await api.post("/user/kyc", kycDetails);
    return { success: true, message: response.data.message || "KYC submitted successfully!" };
  } catch (error) {
    return { 
      success: false, 
      message: error.response?.data?.message || "Failed to submit KYC." 
    };
  }
};
