import React, { useState, useEffect } from "react";
import { adminApi } from "@/services/apiClient";

export default function AdminModels() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const fetchModels = async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const res = await adminApi.listModels();
      setModels(res.items || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load model registry from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0b1c30] tracking-tight">AI Model Version Registry</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#eff6ff] text-[#1e40af] border border-[#dbeafe]">
              Weight Provenance
            </span>
          </div>
          <p className="text-xs text-[#64748b] mt-0.5">
            Registered deep learning checkpoint architectures, verification checksums, and deployment statuses.
          </p>
        </div>

        <button
          onClick={fetchModels}
          disabled={loading}
          className="p-2 border border-[#d8e3ed] bg-white rounded-lg hover:bg-slate-50 transition"
          title="Refresh models"
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

      {/* Model Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {loading ? (
          <div className="col-span-2 py-16 text-center text-xs text-slate-500">Loading model registry...</div>
        ) : models.length === 0 ? (
          <div className="col-span-2 py-16 text-center text-xs text-slate-500">No models registered yet.</div>
        ) : (
          models.map((m) => (
            <div key={m.id} className="bg-white rounded-xl border border-[#e2e8f0] p-5 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs font-bold text-[#0f766e]">Kind: {m.kind}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                    m.is_active ? "bg-emerald-50 text-emerald-800 border border-emerald-200" : "bg-slate-100 text-slate-600"
                  }`}>
                    {m.is_active ? "Active Serving" : "Registered"}
                  </span>
                </div>

                <h3 className="text-base font-bold text-[#0b1c30]">{m.version}</h3>
                <p className="text-xs text-[#64748b] mt-1">{m.notes || "Biomarker classification model"}</p>

                <div className="mt-4 pt-3 border-t border-[#f1f5f9] grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-[10px] text-[#64748b]">Model ID</span>
                    <div className="font-mono font-bold text-[#0b1c30]">#{m.id}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-[#64748b]">Registered Date</span>
                    <div className="font-mono text-[11px] text-[#475569]">{m.created_at ? new Date(m.created_at).toLocaleDateString() : "N/A"}</div>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
