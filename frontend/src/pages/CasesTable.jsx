import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { casesApi } from "@/services/apiClient";

export default function CasesTable() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("All");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCases, setTotalCases] = useState(0);

  const fetchCases = async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const params = {
        page,
        page_size: pageSize,
      };
      if (filterStatus !== "All") {
        params.status = filterStatus;
      }

      const res = await casesApi.listCases(params);
      setCases(res.items || []);
      setTotalCases(res.total || 0);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load clinical cases from the database.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [page, filterStatus]);

  const filteredCases = cases.filter((c) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    const idMatch = String(c.id).includes(term) || `case #${c.id}`.toLowerCase().includes(term);
    const eyeMatch = c.eye && c.eye.toLowerCase().includes(term);
    const statusMatch = c.status && c.status.toLowerCase().includes(term);
    return idMatch || eyeMatch || statusMatch;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case "graded":
        return {
          bg: "bg-emerald-50 text-emerald-800 border-emerald-200",
          dot: "bg-emerald-500",
          label: "Graded (AI Complete)",
        };
      case "in_review":
        return {
          bg: "bg-purple-50 text-purple-800 border-purple-200",
          dot: "bg-purple-500",
          label: "In Review",
        };
      case "reviewed":
        return {
          bg: "bg-teal-50 text-teal-800 border-teal-200",
          dot: "bg-teal-600",
          label: "Clinician Signed",
        };
      case "needs_recapture":
        return {
          bg: "bg-amber-50 text-amber-800 border-amber-200",
          dot: "bg-amber-500",
          label: "Needs Recapture",
        };
      case "uploaded":
      default:
        return {
          bg: "bg-blue-50 text-blue-800 border-blue-200",
          dot: "bg-blue-500",
          label: "Uploaded / Queued",
        };
    }
  };

  const formatTimestamp = (isoString) => {
    if (!isoString) return "N/A";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZoneName: "short",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold text-[#64748b] tracking-wider uppercase">
            Clinical Worklist &bull; Decision Support
          </div>
          <h1 className="text-xl font-bold text-[#0b1c30] tracking-tight">Active Screening Studies</h1>
          <p className="text-xs text-[#64748b] mt-0.5">
            Real-time screening database with quality validation checks, severity staging, and triage pathways.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/upload"
            className="px-3.5 py-2 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs transition"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>New Study Ingestion</span>
          </Link>
          <button
            onClick={fetchCases}
            disabled={loading}
            className="p-2 border border-[#d8e3ed] hover:bg-[#f8fafc] text-[#475569] rounded-lg transition"
            title="Refresh database"
          >
            <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2 shadow-xs">
          <svg className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="leading-tight font-medium">{errorMessage}</div>
        </div>
      )}

      {/* Filters & Search */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between shadow-xs">
        <div className="relative flex-1 max-w-md">
          <span className="absolute left-3 top-2.5 text-[#94a3b8]">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by Case ID (#1, #2), eye, or status..."
            className="w-full pl-9 pr-3 py-2 text-xs border border-[#d9e2ec] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e]"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
          {[
            { id: "All", label: "All Statuses" },
            { id: "uploaded", label: "Queued" },
            { id: "graded", label: "Graded" },
            { id: "in_review", label: "In Review" },
            { id: "needs_recapture", label: "Recapture" },
            { id: "reviewed", label: "Signed" },
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => {
                setFilterStatus(st.id);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition cursor-pointer ${
                filterStatus === st.id
                  ? "bg-[#084c47] text-white shadow-xs"
                  : "bg-[#f1f5f9] text-[#475569] hover:bg-[#e2e8f0]"
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center text-center">
            <div className="w-8 h-8 border-3 border-[#0f766e]/20 border-t-[#0f766e] rounded-full animate-spin mb-2.5"></div>
            <div className="text-xs font-semibold text-[#0b1c30]">Loading clinical studies from database...</div>
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="py-16 flex flex-col items-center justify-center text-center px-4">
            <div className="w-12 h-12 rounded-full bg-[#f1f5f9] text-[#94a3b8] flex items-center justify-center mb-3">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-xs font-bold text-[#0b1c30]">No screening cases found</h3>
            <p className="text-xs text-[#64748b] mt-1 max-w-sm">
              {filterStatus !== "All" || search
                ? "No studies matched the selected filter or search keyword."
                : "No cases have been uploaded yet in your workstation queue."}
            </p>
            <Link
              to="/upload"
              className="mt-4 px-4 py-2 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold transition"
            >
              Upload First Case
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#f8fafc] border-b border-[#e2e8f0] text-[#64748b] font-semibold">
                  <th className="py-3 px-4">Case ID</th>
                  <th className="py-3 px-4">Ingestion Time</th>
                  <th className="py-3 px-4">Eye</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">System Flags</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f1f5f9]">
                {filteredCases.map((c) => {
                  const badge = getStatusBadge(c.status);
                  return (
                    <tr key={c.id} className="hover:bg-[#f8fafc]/80 transition">
                      <td className="py-3 px-4 font-mono font-bold text-[#0f766e]">
                        <Link to={`/cases/${c.id}`} className="hover:underline flex items-center gap-1.5">
                          <span>Case #{c.id}</span>
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-[#475569]">{formatTimestamp(c.created_at)}</td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-[#0b1c30] uppercase">
                          {c.eye ? (c.eye === "right" ? "OD (Right)" : "OS (Left)") : "Unspecified"}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${badge.bg}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`}></span>
                          <span>{badge.label}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {c.flags && c.flags.length > 0 ? (
                          <div className="flex gap-1 flex-wrap">
                            {c.flags.map((flag, idx) => (
                              <span key={idx} className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-mono">
                                {flag}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-[#94a3b8] text-[11px]">None</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to={`/cases/${c.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1 bg-[#f0f9f8] hover:bg-[#e0f4f1] text-[#0f766e] border border-[#bbf0e8] rounded-md font-semibold text-[11px] transition"
                        >
                          <span>Open Review</span>
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                          </svg>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="px-4 py-3 bg-[#f8fafc] border-t border-[#e2e8f0] flex items-center justify-between text-xs text-[#64748b]">
          <div>
            Showing <strong className="text-[#0b1c30]">{filteredCases.length}</strong> of{" "}
            <strong className="text-[#0b1c30]">{totalCases}</strong> total cases
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page <= 1 || loading}
              className="px-3 py-1 bg-white border border-[#d9e2ec] rounded-md text-xs font-semibold text-[#334155] hover:bg-[#f1f5f9] disabled:opacity-40 transition"
            >
              Previous
            </button>
            <span className="font-mono px-2 font-semibold text-[#0b1c30]">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * pageSize >= totalCases || loading}
              className="px-3 py-1 bg-white border border-[#d9e2ec] rounded-md text-xs font-semibold text-[#334155] hover:bg-[#f1f5f9] disabled:opacity-40 transition"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
