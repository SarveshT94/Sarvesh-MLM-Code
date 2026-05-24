import api from "./api";

export const fetchNetworkData = async () => {
  try {
    // 🔥 FIXED: Using secure "/me" routes instead of trusting frontend IDs
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
    return { success: false, totalCount: 0, directTeam: [], tree: [] };
  }
};
