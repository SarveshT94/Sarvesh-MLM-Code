import api from "./api";

export const fetchNetworkData = async (userId) => {
  try {
    const [teamRes, genealogyRes] = await Promise.all([
      api.get(`/team/${userId}`), // Notice we removed /api/ here
      api.get(`/genealogy/${userId}`)
    ]);
    return { success: true, totalCount: teamRes.data.total_team || 0, directTeam: teamRes.data.direct_team || [], tree: genealogyRes.data.team_tree || [] };
  } catch (error) {
    return { success: false, totalCount: 0, directTeam: [], tree: [] };
  }
};
