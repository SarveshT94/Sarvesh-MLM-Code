import api from "./api";

export const fetchNetworkData = async () => {
  try {
    const [teamRes, genealogyRes] = await Promise.all([
      api.get("/team/me"),        
      api.get("/genealogy/me")    
    ]);
    
    // 🔥 DEBUGGING LOGS: This will prove what the backend is sending
    console.log("🔥 RAW TEAM DATA:", teamRes.data);
    console.log("🔥 RAW TREE DATA:", genealogyRes.data);
    
    return {
      success: true,
      totalCount: teamRes.data.total_team || 0,
      directTeam: teamRes.data.direct_team || [],
      tree: genealogyRes.data.team_tree || {}
    };
  } catch (error) {
    console.error("Network data fetch error:", error);
    return { success: false, totalCount: 0, directTeam: [], tree: {} };
  }
};

export const fetchUplineData = async () => {
  try {
    const res = await api.get("/team/upline"); 
    console.log("🔥 RAW UPLINE DATA:", res.data);
    return {
      success: true,
      data: res.data || null
    };
  } catch (error) {
    console.error("Upline fetch error:", error);
    return { success: false, data: null };
  }
};
