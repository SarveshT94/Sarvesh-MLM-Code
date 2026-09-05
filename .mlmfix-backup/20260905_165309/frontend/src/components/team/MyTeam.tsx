"use client";

/*
 * frontend/src/components/team/MyTeam.tsx  —  NEW
 * ------------------------------------------------------------------
 * "My Team" drill-down widget for the Next.js member dashboard.
 *
 *   - Renders YOUR root node with the 4 stat tiles (Total Team,
 *     Direct Referrals, Active, Rank) — same layout as your mockup.
 *   - Clicking a member card (e.g. Member B) calls the SAME endpoint
 *     with that member's id and the card transforms in place ->
 *     "the audit drill follows the selected member".
 *   - A breadcrumb (You / Member A / Member B ...) lets you walk back
 *     up without losing context.
 *   - Only ONE level is fetched per click (paginated, 12 per page) so
 *     it stays instant even at 100k+ users.
 *
 * Requires backend endpoint:  GET /api/team/node?user_id=<id>&page=
 * (see app/routes/team_routes.py).
 */

import { useCallback, useEffect, useState } from "react";
import api from "@/services/api";

type Member = {
  id: string;
  full_name?: string;
  referral_code?: string;
  rank?: string;
  is_active?: boolean;
  total_team_count?: number;
  direct_count?: number;
};

type NodeData = {
  node: { id: string; label: string; full_name?: string; rank?: string; package_name?: string };
  stats: { total_team: number; direct_referrals: number; active: number; rank: string };
  children: Member[];
  pagination: { page: number; pages: number; total: number };
};

type Crumb = { id: string; name: string };

function StatTile({ label, value, rank }: { label: string; value: React.ReactNode; rank?: boolean }) {
  return (
    <div className="flex-1 min-w-[140px] bg-white rounded-2xl border border-slate-200 px-5 py-4 shadow-sm">
      <div className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">{label}</div>
      <div className={`text-2xl font-extrabold mt-1 ${rank ? "text-amber-600" : "text-slate-900"}`}>
        {value}
      </div>
    </div>
  );
}

export default function MyTeam() {
  const [data, setData] = useState<NodeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [rank, setRank] = useState("");
  const [search, setSearch] = useState("");
  const [trail, setTrail] = useState<Crumb[]>([]);

  const currentId = trail.length ? trail[trail.length - 1].id : "";

  const load = useCallback(
    async (id: string, pageNum = 1) => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number> = { page: pageNum, page_size: 12 };
        if (id) params.user_id = id;
        if (status) params.status = status;
        if (rank) params.rank = rank;
        const res = await api.get("/team/node", { params });
        const payload = res.data?.data;
        if (!payload) throw new Error("No data");
        setData(payload);
        setPage(pageNum);
        setTrail((prev) => {
          const nodeId = String(payload.node.id);
          const idx = prev.findIndex((c) => c.id === nodeId);
          if (idx >= 0) return prev.slice(0, idx + 1);
          if (prev.length === 0) {
            return [{ id: nodeId, name: payload.node.full_name || "You" }];
          }
          return [...prev, { id: nodeId, name: payload.node.full_name || payload.node.label }];
        });
      } catch (e: any) {
        setError(e?.response?.data?.message || "Failed to load team");
      } finally {
        setLoading(false);
      }
    },
    [status, rank]
  );

  // Initial load (logged-in user's own root).
  useEffect(() => {
    load("", 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drill = (m: Member) => load(String(m.id), 1);
  const goCrumb = (i: number) => {
    const target = trail[i];
    setTrail(trail.slice(0, i + 1));
    load(String(target.id), 1);
  };

  const filtered = (data?.children || []).filter((m) => {
    const q = search.trim().toLowerCase();
    return !q || (m.full_name || "").toLowerCase().includes(q) ||
           (m.referral_code || "").toLowerCase().includes(q);
  });

  const initials = (name?: string) => (name ? name[0].toUpperCase() : "M");

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-xl font-extrabold text-slate-900 mb-4">My Team</h2>

      {/* Stat tiles */}
      <div className="flex gap-4 flex-wrap mb-4">
        <StatTile label="Total Team" value={(data?.stats.total_team ?? 0).toLocaleString("en-IN")} />
        <StatTile label="Direct Referrals" value={(data?.stats.direct_referrals ?? 0).toLocaleString("en-IN")} />
        <StatTile label="Active" value={(data?.stats.active ?? 0).toLocaleString("en-IN")} />
        <StatTile label="Rank" value={data?.stats.rank || "Distributor"} rank />
      </div>

      {/* Breadcrumb */}
      {trail.length > 1 && (
        <div className="text-sm text-slate-500 mb-3 flex flex-wrap items-center gap-1">
          {trail.map((c, i) => (
            <span key={c.id}>
              {i > 0 && <span className="mx-1">/</span>}
              {i === trail.length - 1 ? (
                <strong className="text-slate-900">{c.name}</strong>
              ) : (
                <button className="text-indigo-600 font-semibold hover:underline" onClick={() => goCrumb(i)}>
                  {i === 0 ? "You" : c.name}
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap items-center mb-4">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search member 🔍"
          className="flex-1 min-w-[220px] border border-slate-200 rounded-xl px-4 py-2 text-sm"
        />
        <select value={rank} onChange={(e) => { setRank(e.target.value); }}
          className="border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white">
          <option value="">Rank ▾</option>
          {["Bronze","Silver","Gold","Emerald","Platinum","Ruby","Diamond","Crown Diamond"].map(r =>
            <option key={r}>{r}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white">
          <option value="">Status ▾</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Node card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-200 bg-gradient-to-r from-indigo-50 to-white">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-extrabold text-slate-900">
              {data?.node.label === "YOU" ? "YOU" : data?.node.label}
              {" — "}{data?.node.full_name}
            </span>
          </div>
          <div className="text-sm text-slate-500 mt-1 flex gap-4 flex-wrap">
            <span>🏆 {data?.node.rank || "Distributor"}</span>
            {data?.node.package_name && <span>📦 {data.node.package_name} Plan</span>}
            <span>👥 {data?.stats.total_team.toLocaleString("en-IN")} Team Members</span>
          </div>
        </div>

        <div className="px-6 pt-4 font-bold text-slate-900 text-sm">Level 1</div>

        <div className={`p-6 grid gap-4 grid-cols-[repeat(auto-fill,minmax(220px,1fr))] ${loading ? "opacity-60" : ""}`}>
          {error && <div className="col-span-full text-center text-red-600 py-8">{error}</div>}
          {!error && filtered.length === 0 && !loading && (
            <div className="col-span-full text-center text-slate-400 py-10">No direct members yet.</div>
          )}
          {filtered.map((m) => (
            <button
              key={m.id}
              onClick={() => drill(m)}
              className="text-left border border-slate-200 rounded-2xl p-4 hover:border-indigo-500 hover:shadow-lg hover:-translate-y-0.5 transition bg-white">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 font-extrabold flex items-center justify-center">
                  {initials(m.full_name)}
                </div>
                <div className="min-w-0">
                  <div className="font-bold text-slate-900 text-sm truncate">{m.full_name || "Member " + m.id}</div>
                  <span className="font-mono text-[11px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                    {m.referral_code || m.id}
                  </span>
                </div>
                <span className={`ml-auto text-[11px] font-bold px-2 py-0.5 rounded-full ${
                  m.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {m.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="text-2xl font-extrabold text-slate-900 text-center my-1">
                {(m.total_team_count ?? 0).toLocaleString("en-IN")}
              </div>
              <div className="text-center text-[11px] uppercase tracking-wide text-slate-500">Team Members</div>
              <div className="mt-2 text-center text-xs font-bold text-indigo-600 border-t border-dashed border-slate-200 pt-2">
                Drill ↓
              </div>
            </button>
          ))}
        </div>

        {/* Pager */}
        <div className="flex justify-between items-center px-6 py-4 border-t border-slate-200">
          <button
            disabled={page <= 1 || loading}
            onClick={() => load(currentId, page - 1)}
            className="border border-slate-200 rounded-lg px-4 py-2 font-semibold text-sm disabled:opacity-40">
            ← Prev
          </button>
          <span className="text-xs text-slate-500">
            Page {page} of {data?.pagination.pages || 1} · {data?.pagination.total || 0} directs
          </span>
          <button
            disabled={page >= (data?.pagination.pages || 1) || loading}
            onClick={() => load(currentId, page + 1)}
            className="border border-slate-200 rounded-lg px-4 py-2 font-semibold text-sm disabled:opacity-40">
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
