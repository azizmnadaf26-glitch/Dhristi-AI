import React, { useState, useEffect } from "react";
import { adminApi } from "@/services/apiClient";

export default function AdminAudit() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [outcomeFilter, setOutcomeFilter] = useState("All");
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const fetchAudit = async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const params = {
        page,
        page_size: pageSize,
      };
      if (outcomeFilter !== "All") {
        params.outcome = outcomeFilter;
      }
      const res = await adminApi.listAudit(params);
      setLogs(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load compliance audit logs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, [page, outcomeFilter]);

  const getOutcomeBadge = (outcome) => {
    switch (outcome) {
      case "success":
        return "bg-emerald-50 text-emerald-800 border-emerald-200";
      case "denied":
        return "bg-amber-50 text-amber-800 border-amber-200";
      case "failure":
      default:
        return "bg-rose-50 text-rose-800 border-rose-200";
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0b1c30] tracking-tight">System Compliance &amp; Security Audit Trail</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#f0f9f8] text-[#0f766e] border border-[#d1ebe7]">
              Append-Only Ledger
            </span>
          </div>
          <p className="text-xs text-[#64748b] mt-0.5">
            Immutable forensic record of all logins, uploads, clinical reviews, role updates, and system decisions.
          </p>
        </div>

        <button
          onClick={fetchAudit}
          disabled={loading}
          className="p-2 border border-[#d8e3ed] bg-white rounded-lg hover:bg-slate-50 transition"
          title="Refresh audit logs"
        >
          <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2 shadow-xs">
          <svg className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="leading-tight font-medium">{errorMessage}</div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-2">
          {["All", "success", "denied", "failure"].map((opt) => (
            <button
              key={opt}
              onClick={() => {
                setOutcomeFilter(opt);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition cursor-pointer ${
                outcomeFilter === opt
                  ? "bg-[#084c47] text-white shadow-xs"
                  : "bg-[#f1f5f9] text-[#475569] hover:bg-[#e2e8f0]"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        <div className="text-xs text-[#64748b]">Total events: <strong className="text-[#0b1c30]">{total}</strong></div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-500">Loading audit ledger...</div>
        ) : logs.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-500">No audit events found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#f8fafc] text-[#64748b] font-semibold border-b border-[#e2e8f0]">
                  <th className="py-3 px-4">Event ID</th>
                  <th className="py-3 px-4">Timestamp (UTC)</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Actor ID</th>
                  <th className="py-3 px-4">Target Object</th>
                  <th className="py-3 px-4">Outcome</th>
                  <th className="py-3 px-4">Request ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f1f5f9]">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[#f8fafc]/80 transition">
                    <td className="py-3 px-4 font-mono font-bold text-[#0f766e]">#{log.id}</td>
                    <td className="py-3 px-4 text-[#475569] font-mono">{log.created_at || "N/A"}</td>
                    <td className="py-3 px-4 font-semibold text-[#0b1c30]">{log.action}</td>
                    <td className="py-3 px-4 text-[#475569]">{log.actor_id ? `User #${log.actor_id}` : "System / Anonymous"}</td>
                    <td className="py-3 px-4 text-[#64748b]">
                      {log.object_type ? `${log.object_type} #${log.object_id}` : "—"}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${getOutcomeBadge(log.outcome)}`}>
                        {log.outcome}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-[10px] text-slate-400 truncate max-w-[120px]">
                      {log.request_id || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer */}
        <div className="px-4 py-3 bg-[#f8fafc] border-t border-[#e2e8f0] flex items-center justify-between text-xs text-[#64748b]">
          <div>
            Page <strong className="text-[#0b1c30]">{page}</strong> of <strong className="text-[#0b1c30]">{Math.max(1, Math.ceil(total / pageSize))}</strong>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="px-3 py-1 bg-white border border-[#d9e2ec] rounded text-xs font-semibold text-slate-700 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * pageSize >= total || loading}
              className="px-3 py-1 bg-white border border-[#d9e2ec] rounded text-xs font-semibold text-slate-700 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
