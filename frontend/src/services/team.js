// src/services/team.js
import api from "./api";

export const fetchNetworkData = async () => {
  try {
    // 🔥 REPLACE these with your actual backend endpoints
    const [teamRes, genealogyRes] = await Promise.all([
      api.get("/api/team/me"),        // <-- Change this
      api.get("/api/genealogy/me")    // <-- Change this
    ]);
    return {
      success: true,
      totalCount: teamRes.data.total_team || 0,
      directTeam: teamRes.data.direct_team || [],
      tree: genealogyRes.data.team_tree || []
    };
  } catch (error) {
    return { success: false, totalCount: 0, directTeam: [], tree: [] };
  }
};

export const fetchUplineData = async () => {
  try {
    // 🔥 REPLACE with your actual upline endpoint
    const res = await api.get("/api/team/upline"); // <-- Change this
    return {
      success: true,
      data: res.data || null
    };
  } catch (error) {
    return { success: false, data: null };
  }
};
