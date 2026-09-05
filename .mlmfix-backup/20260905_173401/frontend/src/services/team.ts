import api from "./api";

/*
 * frontend/src/services/team.ts — REWRITE (drop-in for services/team.js)
 *
 * Keeps fetchNetworkData / fetchUplineData for the existing dashboard, and
 * adds fetchTeamNode for the new drill-down <MyTeam /> component.
 *
 * `userId` omitted  -> the logged-in member's own root node.
 * `userId` provided -> that member's node (admins only for other ids).
 */

export type TeamNodeParams = {
  userId?: string | number;
  page?: number;
  pageSize?: number;
  rank?: string;
  status?: string;
};

export const fetchTeamNode = async ({
  userId,
  page = 1,
  pageSize = 12,
  rank,
  status,
}: TeamNodeParams) => {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (userId) params.user_id = userId;
  if (rank) params.rank = rank;
  if (status) params.status = status;

  const res = await api.get("/team/node", { params });
  if (!res.data?.success) {
    throw new Error(res.data?.message || "Failed to load team");
  }
  return res.data.data;
};

export const fetchNetworkData = async () => {
  try {
    const [teamRes, genealogyRes] = await Promise.all([
      api.get("/team/me"),
      api.get("/genealogy/me"),
    ]);

    const totalTeam =
      teamRes.data?.total_team ?? teamRes.data?.totalCount ?? teamRes.data?.count ?? 0;
    const directTeam = teamRes.data?.direct_team ?? teamRes.data?.directs ?? [];
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
      tree: typeof rawTree === "object" && rawTree !== null ? rawTree : {},
    };
  } catch (error) {
    console.error("Network data fetch error:", error);
    return { success: false, totalCount: 0, directTeam: [], tree: {} };
  }
};

export const fetchUplineData = async () => {
  try {
    const res = await api.get("/team/upline");
    return { success: true, data: res.data?.data || res.data || null };
  } catch (error) {
    console.error("Upline fetch error:", error);
    return { success: false, data: null };
  }
};
