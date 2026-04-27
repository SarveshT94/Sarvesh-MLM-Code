import api from "./api";

export const fetchUserRank = async () => {
  try {
    const response = await api.get("/user/rank");
    return { success: true, data: response.data.data };
  } catch (error) {
    console.error("Rank Fetch Error:", error);
    return { success: false, data: null };
  }
};
