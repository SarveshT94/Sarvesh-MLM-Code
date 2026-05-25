// src/services/team.js
import api from "./api";

export const fetchNetworkData = async () => {
  try {
    // 🔥 FIXED: Removed the extra "/api" prefix
    const [teamRes, genealogyRes] = await Promise.all([
      api.get("/team/me"),        
      api.get("/genealogy/me")    
    ]);
    
    return {
      success: true,
      totalCount: teamRes.data.total_team || 0,
      directTeam: teamRes.data.direct_team || [],
      tree: genealogyRes.data.team_tree || []
    };
  } catch (error) {
    console.error("Network data fetch error:", error);
    return { success: false, totalCount: 0, directTeam: [], tree: [] };
  }
};

export const fetchUplineData = async () => {
  try {
    // 🔥 FIXED: Removed the extra "/api" prefix
    const res = await api.get("/team/upline"); 
    return {
      success: true,
      data: res.data || null
    };
  } catch (error) {
    console.error("Upline fetch error:", error);
    return { success: false, data: null };
  }
};
