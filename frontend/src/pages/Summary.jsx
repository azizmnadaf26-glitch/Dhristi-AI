import React, { useState, useEffect } from "react";
import { summaryApi } from "@/services/apiClient";

export default function Summary() {
  const [timeFilter, setTimeFilter] = useState("Today");
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const fetchSummary = async () => {
    setLoading(true);
    setErrorMessage("");

    let dateFrom = null;
    const today = new Date();
    if (timeFilter === "Today") {
      dateFrom = today.toISOString().split("T")[0];
    } else if (timeFilter === "Past 7 Days") {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      dateFrom = d.toISOString().split("T")[0];
    } else if (timeFilter === "Past 30 Days") {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      dateFrom = d.toISOString().split("T")[0];
    }

    try {
      const data = await summaryApi.getSummary(dateFrom);
      setSummaryData(data);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load operational telemetry summary.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [timeFilter]);

  const totalCases = summaryData?.total_cases ?? 0;
  const byStatus = summaryData?.by_status ?? {};
  const predictions = summaryData?.predictions ?? { by_grade: {} };
  const decisions = summaryData?.latest_review_decisions ?? {};

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold text-[#64748b] tracking-wider uppercase">
            Operational Telemetry &bull; Screening Analytics
          </div>
          <h1 className="text-xl font-bold text-[#0b1c30] tracking-tight">Operational Fleet Summary</h1>
          <p className="text-xs text-[#64748b] mt-0.5">
            Real-time screening database throughput, queue status transitions, and clinician triage statistics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center bg-[#f1f5f9] p-0.5 rounded-lg border border-[#e2e8f0]">
            {["Today", "Past 7 Days", "Past 30 Days", "All Time"].map((tab) => (
              <button
                key={tab}
                onClick={() => setTimeFilter(tab)}
                className={`px-3 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                  timeFilter === tab
                    ? "bg-[#084c47] text-white shadow-xs"
                    : "text-[#64748b] hover:text-[#0b1c30]"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <button
            onClick={fetchSummary}
            disabled={loading}
            className="p-1.5 border border-[#d8e3ed] bg-white rounded-lg hover:bg-slate-50 transition"
            title="Refresh statistics"
          >
            <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
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

      {/* Metric Cards Top Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 shadow-xs">
          <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider">Total Ingested Studies</div>
          <div className="text-2xl font-bold text-[#0b1c30] mt-1">{totalCases}</div>
          <div className="text-[11px] text-[#0f766e] mt-1 font-semibold flex items-center gap-1">
            <span>Verified in screening database</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 shadow-xs">
          <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider">AI Graded Studies</div>
          <div className="text-2xl font-bold text-emerald-700 mt-1">{byStatus.graded || 0}</div>
          <div className="text-[11px] text-emerald-600 mt-1 font-semibold">
            Quality checked &amp; staged
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 shadow-xs">
          <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider">Referable DR Detected</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">{predictions.referable || 0}</div>
          <div className="text-[11px] text-amber-700 mt-1 font-semibold">
            Grade &ge; 2 threshold
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 shadow-xs">
          <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider">Clinician Reviewed</div>
          <div className="text-2xl font-bold text-teal-700 mt-1">{byStatus.reviewed || 0}</div>
          <div className="text-[11px] text-[#64748b] mt-1 font-medium">
            Signed specialist assessments
          </div>
        </div>
      </div>

      {/* Status Breakdown & Severity Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Status Distribution */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-[#e2e8f0] p-5 shadow-xs flex flex-col gap-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#f1f5f9]">
            <h2 className="text-xs font-bold text-[#0b1c30]">Worklist Status Pipeline</h2>
            <span className="text-[10px] font-mono text-[#64748b]">Live Lifecycle</span>
          </div>

          <div className="flex flex-col gap-3">
            {[
              { key: "uploaded", label: "Uploaded / Queued for AI", count: byStatus.uploaded || 0, color: "bg-blue-500" },
              { key: "graded", label: "Graded by Biomarker Engine", count: byStatus.graded || 0, color: "bg-emerald-500" },
              { key: "in_review", label: "In Specialist Review", count: byStatus.in_review || 0, color: "bg-purple-500" },
              { key: "reviewed", label: "Clinician Signed Off", count: byStatus.reviewed || 0, color: "bg-teal-600" },
              { key: "needs_recapture", label: "Needs Image Recapture", count: byStatus.needs_recapture || 0, color: "bg-amber-500" },
            ].map((item) => (
              <div key={item.key} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#334155]">{item.label}</span>
                  <span className="font-bold text-[#0b1c30]">{item.count}</span>
                </div>
                <div className="w-full bg-[#f1f5f9] h-2 rounded-full overflow-hidden">
                  <div
                    className={`${item.color} h-full rounded-full transition-all duration-300`}
                    style={{ width: `${totalCases > 0 ? Math.round((item.count / totalCases) * 100) : 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Severity Grade Distribution */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-[#e2e8f0] p-5 shadow-xs flex flex-col gap-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#f1f5f9]">
            <h2 className="text-xs font-bold text-[#0b1c30]">Severity Grade Distribution (ICDR)</h2>
            <span className="text-[10px] font-mono text-[#64748b]">Predictions: {predictions.total || 0}</span>
          </div>

          <div className="flex flex-col gap-3">
            {[
              { grade: "0", label: "Level 0: No apparent retinopathy", count: predictions.by_grade?.["0"] || 0, color: "bg-slate-400" },
              { grade: "1", label: "Level 1: Mild NPDR", count: predictions.by_grade?.["1"] || 0, color: "bg-teal-500" },
              { grade: "2", label: "Level 2: Moderate NPDR (Referable)", count: predictions.by_grade?.["2"] || 0, color: "bg-amber-500" },
              { grade: "3", label: "Level 3: Severe NPDR (Referable)", count: predictions.by_grade?.["3"] || 0, color: "bg-orange-500" },
              { grade: "4", label: "Level 4: Proliferative DR (Urgent)", count: predictions.by_grade?.["4"] || 0, color: "bg-rose-500" },
            ].map((item) => (
              <div key={item.grade} className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#334155]">{item.label}</span>
                  <span className="font-bold text-[#0b1c30]">{item.count}</span>
                </div>
                <div className="w-full bg-[#f1f5f9] h-2 rounded-full overflow-hidden">
                  <div
                    className={`${item.color} h-full rounded-full transition-all duration-300`}
                    style={{ width: `${(predictions.total || 0) > 0 ? Math.round((item.count / (predictions.total || 1)) * 100) : 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Clinician Decision Breakdown */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] p-5 shadow-xs">
        <h2 className="text-xs font-bold text-[#0b1c30] mb-3">Clinician Triage Decisions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          <div className="p-3 bg-[#f0f9f8] rounded-lg border border-[#ccede8]">
            <div className="text-[10px] font-bold uppercase text-[#0f766e]">Confirmed</div>
            <div className="text-lg font-bold text-[#0f766e] mt-0.5">{decisions.confirm || 0}</div>
          </div>
          <div className="p-3 bg-purple-50 rounded-lg border border-purple-200">
            <div className="text-[10px] font-bold uppercase text-purple-700">Overridden</div>
            <div className="text-lg font-bold text-purple-800 mt-0.5">{decisions.override || 0}</div>
          </div>
          <div className="p-3 bg-amber-50 rounded-lg border border-amber-200">
            <div className="text-[10px] font-bold uppercase text-amber-700">Recaptures</div>
            <div className="text-lg font-bold text-amber-800 mt-0.5">{decisions.recapture || 0}</div>
          </div>
          <div className="p-3 bg-rose-50 rounded-lg border border-rose-200">
            <div className="text-[10px] font-bold uppercase text-rose-700">Referred</div>
            <div className="text-lg font-bold text-rose-800 mt-0.5">{decisions.refer || 0}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
