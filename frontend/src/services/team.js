import api from "./api";

export const fetchNetworkData = async () => {
  try {
    const [teamRes, genealogyRes] = await Promise.all([
      api.get("/team/me"),
      api.get("/genealogy/me")
    ]);

    const totalTeam =
      teamRes.data?.total_team ??
      teamRes.data?.totalCount ??
      teamRes.data?.count ??
      0;

    const directTeam =
      teamRes.data?.direct_team ??
      teamRes.data?.directs ??
      [];

    const rawTree =
      genealogyRes.data?.team_tree ??
      genealogyRes.data?.tree ??
      genealogyRes.data?.data ??
      genealogyRes.data ??
      {};

    return {
      success: true,
      totalCount: totalTeam,
      directTeam: Array.isArray(directTeam) ? directTeam : [],
      tree: typeof rawTree === "object" && rawTree !== null ? rawTree : {}
    };
  } catch (error) {
    console.error("Network data fetch error:", error);
    return {
      success: false,
      totalCount: 0,
      directTeam: [],
      tree: {}
    };
  }
};

export const fetchUplineData = async () => {
  try {
    const res = await api.get("/team/upline");
    return {
      success: true,
      data: res.data?.data || res.data || null
    };
  } catch (error) {
    console.error("Upline fetch error:", error);
    return {
      success: false,
      data: null
    };
  }
};
