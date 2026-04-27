import api from "./api";

export const fetchWalletData = async (userId) => {
  try {
    const [balanceRes, historyRes] = await Promise.all([
      api.get(`/wallet/${userId}`), // Notice we removed /api/ here
      api.get(`/wallet/${userId}/history`)
    ]);
    return { success: true, balance: balanceRes.data.wallet_balance || 0, history: historyRes.data.transactions || [] };
  } catch (error) {
    return { success: false, balance: 0, history: [] };
  }
};

export const submitWithdrawal = async (amount, payoutMethod, payoutDetails) => {
  try {
    const response = await api.post("/wallet/withdraw", { 
      amount, payout_method: payoutMethod, payout_details: JSON.stringify(payoutDetails)
    });
    return { success: true, message: response.data.message };
  } catch (error) {
    return { success: false, message: error.response?.data?.message || "Withdrawal failed." };
  }
};

export const submitP2PTransfer = async (receiverIdentifier, amount) => {
  try {
    const response = await api.post("/wallet/transfer", { receiver: receiverIdentifier, amount: amount });
    return { success: true, message: response.data.message };
  } catch (error) {
    return { success: false, message: error.response?.data?.message || "Transfer failed." };
  }
};
