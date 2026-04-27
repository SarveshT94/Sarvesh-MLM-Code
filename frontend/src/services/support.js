import api from "./api";

export const fetchTickets = async () => {
  try {
    const response = await api.get("/support/tickets");
    return { success: true, data: response.data.data || [] };
  } catch (error) {
    console.error("Error fetching tickets", error);
    return { success: false, data: [] };
  }
};

export const createTicket = async (subject, message) => {
  try {
    const response = await api.post("/support/tickets", { subject, message });
    return { success: true, message: response.data.message };
  } catch (error) {
    return { success: false, message: error.response?.data?.message || "Failed to submit ticket." };
  }
};
