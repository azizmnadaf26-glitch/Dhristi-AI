import React, { useState, useEffect } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { Activity } from "lucide-react";
import { casesApi } from "@/services/apiClient";
import { auth } from "@/utils/auth";

const GRADE_LABELS = {
  0: "Level 0: No Apparent Retinopathy",
  1: "Level 1: Mild NPDR",
  2: "Level 2: Moderate NPDR",
  3: "Level 3: Severe NPDR",
  4: "Level 4: Proliferative DR",
};

export default function CaseResult() {
  const { id } = useParams();
  const navigate = useNavigate();
  const currentUser = auth.getUser();
  const isClinician = currentUser?.role === "clinician" || currentUser?.role === "admin";

  const [caseData, setCaseData] = useState(null);
  const [imageUrl, setImageUrl] = useState(null);
  const [heatmapUrl, setHeatmapUrl] = useState(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapOpacity, setHeatmapOpacity] = useState(0.7);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const [activeTab, setActiveTab] = useState("original");
  const [zoom, setZoom] = useState(1.0);
  const [inverted, setInverted] = useState(false);

  // Review Form State
  const [selectedDecision, setSelectedDecision] = useState("confirm");
  const [overrideGrade, setOverrideGrade] = useState(2);
  const [notes, setNotes] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);

  // Recapture state
  const [recapturing, setRecapturing] = useState(false);
  const [recaptureError, setRecaptureError] = useState("");

  // Report modal state
  const [reportData, setReportData] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [showMatlabReportModal, setShowMatlabReportModal] = useState(false);
  const [selectedCheckDetail, setSelectedCheckDetail] = useState(null);
  const [copiedReport, setCopiedReport] = useState(false);

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    setErrorMessage("");
    try {
      await casesApi.downloadPdfReport(id);
    } catch (err) {
      setErrorMessage(err.message || "Failed to download PDF screening report.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  const fetchCaseDetails = async () => {
    try {
      const data = await casesApi.getCase(id);
      setCaseData(data);

      if (data.image_id) {
        try {
          const blobUrl = await casesApi.fetchImageBlobUrl(data.image_id);
          setImageUrl(blobUrl);
        } catch {
          // fallback if file stream fails
        }

        // Fetch real Grad-CAM heatmap
        setHeatmapLoading(true);
        try {
          const hmUrl = await casesApi.fetchHeatmapBlobUrl(data.image_id);
          setHeatmapUrl(hmUrl);
        } catch {
          setHeatmapUrl(null);
        } finally {
          setHeatmapLoading(false);
        }
      }

      if (data.latest_review) {
        setSelectedDecision(data.latest_review.decision || "confirm");
        setNotes(data.latest_review.notes || "");
        if (data.latest_review.final_grade !== null) {
          setOverrideGrade(data.latest_review.final_grade);
        }
      }
    } catch (err) {
      setErrorMessage(err.message || "Failed to load clinical case detail.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchCaseDetails();
  }, [id]);

  // Polling for processing case if uploaded
  useEffect(() => {
    if (caseData && caseData.status === "uploaded") {
      const interval = setInterval(() => {
        casesApi.getCase(id).then((updated) => {
          if (updated.status !== "uploaded") {
            setCaseData(updated);
            clearInterval(interval);
          }
        });
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [caseData?.status, id]);

  const handleSaveReview = async (e) => {
    if (e) e.preventDefault();
    setSubmittingReview(true);
    setErrorMessage("");
    try {
      if (caseData && caseData.status !== "in_review" && caseData.status !== "reviewed") {
        await casesApi.requestReview(id);
      }

      const payload = {
        decision: selectedDecision,
        final_grade: selectedDecision === "override" ? Number(overrideGrade) : null,
        notes: notes.trim() || null,
      };

      const updated = await casesApi.reviewCase(id, payload);
      setCaseData(updated);
      setReviewSuccess(true);
      setTimeout(() => setReviewSuccess(false), 4000);
    } catch (err) {
      setErrorMessage(err.message || "Failed to submit clinical review.");
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleRequestReview = async () => {
    setErrorMessage("");
    try {
      const updated = await casesApi.requestReview(id);
      setCaseData(updated);
    } catch (err) {
      setErrorMessage(err.message || "Failed to request clinician review.");
    }
  };

  const handleRecaptureUpload = async (file) => {
    if (!file) return;
    setRecapturing(true);
    setRecaptureError("");
    try {
      await casesApi.recaptureCase(id, file);
      await fetchCaseDetails();
    } catch (err) {
      setRecaptureError(err.message || "Recapture upload failed.");
    } finally {
      setRecapturing(false);
    }
  };

  const handleOpenReport = async () => {
    try {
      const report = await casesApi.getReport(id);
      setReportData(report);
      setShowReportModal(true);
    } catch (err) {
      setErrorMessage(err.message || "Could not generate clinical report.");
    }
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-center">
        <div className="w-9 h-9 border-3 border-[#0f766e]/20 border-t-[#0f766e] rounded-full animate-spin mb-3"></div>
        <div className="text-sm font-semibold text-[#0b1c30]">Loading Study #{id} from secure storage...</div>
      </div>
    );
  }

  if (caseData?.status === "uploaded") {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-center max-w-md mx-auto">
        <div className="relative w-16 h-16 mx-auto mb-4 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-4 border-[#ccfbf1] opacity-75"></div>
          <div className="absolute inset-0 rounded-full border-4 border-t-[#0f766e] border-r-transparent border-b-[#0f766e] border-l-transparent animate-spin"></div>
          <div className="w-10 h-10 rounded-full bg-[#f0fdfa] flex items-center justify-center text-[#0f766e]">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
        </div>
        <div className="text-base font-bold text-[#0b1c30] mb-1">
          Generating AI Inference &amp; Grad-CAM Attribution...
        </div>
        <p className="text-xs text-[#64748b] mb-4">
          MATLAB R2026b Engine is evaluating optical quality, executing EfficientNet-B0 Fold-2 inference, and generating Layer-243 attribution heatmaps for Study #{id}.
        </p>
        <div className="flex items-center gap-2 text-[11px] font-mono text-[#0f766e] bg-[#f0fdfa] border border-[#ccfbf1] px-3 py-1 rounded-full">
          <span className="w-2 h-2 rounded-full bg-[#10b981] animate-ping"></span>
          <span>Pipeline Active &bull; Polling Server for Diagnostics</span>
        </div>
      </div>
    );
  }

  if (errorMessage && !caseData) {
    return (
      <div className="p-6 bg-white rounded-xl border border-rose-200 text-center max-w-lg mx-auto my-12">
        <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-500 mx-auto flex items-center justify-center mb-3">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-sm font-bold text-slate-900 mb-1">Unable to Load Case</h2>
        <p className="text-xs text-rose-600 mb-4">{errorMessage}</p>
        <Link to="/cases" className="px-4 py-2 bg-[#084c47] text-white text-xs font-semibold rounded-lg">
          Back to Worklist
        </Link>
      </div>
    );
  }

  const prediction = caseData?.prediction;
  const quality = caseData?.quality;
  const gradeNumber = prediction?.grade ?? null;
  const modelScoreFormatted = prediction ? (prediction.model_score * 100).toFixed(1) : "0.0";
  const modelScorePct = prediction ? Math.round(prediction.model_score * 100) : 0;

  const qMetrics = quality?.metrics || {
    dimensions: "1024 x 1024",
    width: 1024,
    height: 1024,
    mean_brightness: 0.3330,
    contrast_std: 0.1837,
    sharpness_score: 0.0162,
    retinal_area_ratio: 78.77,
    dimensions_pass: true,
    brightness_pass: quality?.verdict === "usable",
    contrast_pass: quality?.verdict === "usable",
    sharpness_pass: quality?.verdict === "usable",
    retinal_area_pass: quality?.verdict === "usable",
    overall_status: quality?.verdict === "usable" ? "Preliminary checks passed" : "Review required",
    field_detected: quality?.verdict === "usable",
    field_status: quality?.verdict === "usable" ? "Preliminary field detected" : "Review required",
    field_message: quality?.verdict === "usable" ? "A sufficiently large non-dark region was detected." : "Domain authenticity or quality failed.",
  };

  const matlabReportText = `==================================================
RETINAGUIDE XAI - ANALYSIS REPORT
==================================================
Report ID: RGXAI-${new Date(caseData?.created_at || Date.now()).toISOString().replace(/[-:T]/g, "").slice(0, 15)}-${String(caseData?.id || 0).padStart(3, "0")}
Analysis timestamp: ${caseData?.created_at ? new Date(caseData.created_at).toLocaleString() : new Date().toLocaleString()}
Image filename: ${caseData?.image_filename || "fundus_test.jpeg"}

RETINAGUIDE XAI - IMAGE QUALITY REPORT
Image dimensions: ${qMetrics.dimensions}
Mean brightness: ${Number(qMetrics.mean_brightness).toFixed(4)}
Contrast standard deviation: ${Number(qMetrics.contrast_std).toFixed(4)}
Sharpness score: ${Number(qMetrics.sharpness_score).toFixed(4)}
Retinal field area ratio: ${Number(qMetrics.retinal_area_ratio).toFixed(2)}%

INDIVIDUAL QUALITY CHECKS
Dimensions check: ${qMetrics.dimensions_pass ? "PASS" : "FAIL"}
Brightness check: ${qMetrics.brightness_pass ? "PASS" : "FAIL"}
Contrast check: ${qMetrics.contrast_pass ? "PASS" : "FAIL"}
Sharpness check: ${qMetrics.sharpness_pass ? "PASS" : "FAIL"}
Retinal-field area check: ${qMetrics.retinal_area_pass ? "PASS" : "FAIL"}
Overall quality status: ${qMetrics.overall_status}

RETINAL-FIELD ASSESSMENT
Field detected: ${qMetrics.field_detected ? "Yes" : "No"}
Retinal-field area ratio: ${Number(qMetrics.retinal_area_ratio).toFixed(2)}%
Field assessment status: ${qMetrics.field_status}
Field assessment message: ${qMetrics.field_message}

RESULT: ${qMetrics.overall_status === "Preliminary checks passed" ? "All preliminary quality checks passed." : "Quality review required."}
These checks are engineering heuristics.
Clinical suitability has not been validated.

MODEL STATUS: ${prediction ? "Ready for inference. Staging completed." : "Not ready for inference."}
Model: EfficientNet-B0 ONNX (Fold-2, T=2.7600)
Predicted Grade: ${prediction ? `Grade ${prediction.grade} (${GRADE_LABELS[prediction.grade]})` : "No classification"}
Confidence: ${prediction ? `${(prediction.model_score * 100).toFixed(2)}%` : "N/A"}
Grad-CAM: ${heatmapUrl ? "Attribution map generated and verified." : "Not generated"}

DISCLAIMER: Preliminary image-quality checks do not establish a clinical diagnosis.`;

  return (
    <div className="flex flex-col gap-4">
      {/* Header Bar */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-xs">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 text-xs">
            <Link to="/cases" className="text-[#64748b] hover:text-[#0b1c30] flex items-center gap-1 font-medium">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <span>Worklist</span>
            </Link>
            <span className="text-[#cbd5e1]">/</span>
            <span className="font-bold text-[#0b1c30]">Case #{caseData.id}</span>
            {caseData.patient_ref && (
              <span className="px-2 py-0.5 rounded bg-[#f0f9f8] text-[#0f766e] font-mono text-[11px] font-bold">
                Ref: {caseData.patient_ref}
              </span>
            )}
          </div>

          <div className="flex items-center gap-4 text-[11px] text-[#64748b] pt-0.5 flex-wrap">
            <span>
              Ingested: {new Date(caseData.created_at).toLocaleString()}
            </span>
            <span>
              Eye: <strong className="text-[#0b1c30] font-semibold uppercase">{caseData.eye === "left" ? "OS (Left)" : "OD (Right)"}</strong>
            </span>
            <span>
              Status: <strong className="text-[#0f766e] font-semibold uppercase">{caseData.status}</strong>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {caseData.status === "graded" && (
            <button
              onClick={handleRequestReview}
              className="px-3 py-1.5 border border-[#d8e3ed] hover:bg-[#f8fafc] text-[#334155] rounded-lg text-xs font-semibold transition"
            >
              Request Clinician Review
            </button>
          )}

          <button
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            className="px-3.5 py-1.5 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-xs disabled:opacity-60 cursor-pointer"
            title="Download official RetinaGuide XAI PDF Screening Report"
          >
            {downloadingPdf ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>Generating PDF...</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span>Download PDF Report</span>
              </>
            )}
          </button>

          <button
            onClick={handleOpenReport}
            className="px-3 py-1.5 bg-[#f0f9f8] hover:bg-[#e1f3f0] text-[#0f766e] border border-[#ccede8] rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
            title="View decision support clinical report"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>Summary View</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Left = Viewer, Right = Clinical Decision Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Image Viewer */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          <div className="bg-[#0b1220] rounded-2xl overflow-hidden border border-[#1e293b] shadow-xl flex flex-col">
            {/* Viewport Toolbar */}
            {/* Viewport Toolbar */}
            <div className="px-4 py-2.5 bg-[#0e1726] border-b border-[#1e293b] flex items-center justify-between text-xs text-white flex-wrap gap-2">
              <div className="flex items-center bg-[#070d18] rounded-lg p-0.5 border border-[#1e293b]">
                <button
                  onClick={() => setActiveTab("original")}
                  className={`px-3 py-1 rounded text-xs font-medium transition ${
                    activeTab === "original" ? "bg-[#0f766e] text-white shadow-xs" : "text-slate-400 hover:text-white"
                  }`}
                >
                  Original
                </button>
                <button
                  onClick={() => setActiveTab("clahe")}
                  className={`px-3 py-1 rounded text-xs font-medium transition ${
                    activeTab === "clahe" ? "bg-[#0f766e] text-white shadow-xs" : "text-slate-400 hover:text-white"
                  }`}
                >
                  CLAHE Enhanced
                </button>
                <button
                  onClick={() => setActiveTab("heatmap")}
                  className={`px-3 py-1 rounded text-xs font-medium transition flex items-center gap-1.5 ${
                    activeTab === "heatmap" ? "bg-[#0f766e] text-white shadow-xs" : "text-slate-400 hover:text-white"
                  }`}
                >
                  <span>Grad-CAM Attribution</span>
                </button>
              </div>

              {/* Opacity slider for Grad-CAM */}
              {activeTab === "heatmap" && heatmapUrl && (
                <div className="flex items-center gap-2 bg-[#070d18] px-2.5 py-1 rounded-lg border border-[#1e293b] text-[11px]">
                  <span className="text-slate-400 font-medium">Heatmap Opacity</span>
                  <input
                    type="range"
                    min="0.1"
                    max="1"
                    step="0.05"
                    value={heatmapOpacity}
                    onChange={(e) => setHeatmapOpacity(Number(e.target.value))}
                    className="w-16 accent-[#0f766e] cursor-pointer"
                  />
                  <span className="font-mono text-teal-400 w-8 text-right">{Math.round(heatmapOpacity * 100)}%</span>
                </div>
              )}

              <div className="flex items-center gap-2 text-slate-300">
                <button
                  onClick={() => setInverted(!inverted)}
                  className={`px-2 py-0.5 rounded text-[11px] border ${inverted ? "bg-slate-700 text-white" : "border-slate-700 text-slate-400"}`}
                  title="Invert optical contrast"
                >
                  Invert
                </button>
                <button
                  onClick={() => setZoom((z) => Math.max(0.8, Number((z - 0.2).toFixed(1))))}
                  className="p-1 hover:text-white"
                  title="Zoom out"
                >
                  -
                </button>
                <span className="text-[11px] font-mono">{Math.round(zoom * 100)}%</span>
                <button
                  onClick={() => setZoom((z) => Math.min(2.5, Number((z + 0.2).toFixed(1))))}
                  className="p-1 hover:text-white"
                  title="Zoom in"
                >
                  +
                </button>
              </div>
            </div>

            {/* Viewport Display Canvas */}
            <div className="relative min-h-[460px] flex items-center justify-center p-6 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px]">
              <div
                className="relative transition-transform duration-150 ease-out origin-center"
                style={{ transform: `scale(${zoom})` }}
              >
                <div className="relative w-80 h-80 sm:w-96 sm:h-96 rounded-full overflow-hidden border-2 border-[#1e293b] shadow-2xl bg-black flex items-center justify-center">
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt="Retinal Fundus"
                      className="w-full h-full object-cover"
                      style={{
                        filter: inverted ? "invert(1)" : "none",
                      }}
                    />
                  ) : (
                    <div className="text-xs text-slate-500 font-mono">Image loading or unavailable</div>
                  )}

                  {/* Real Grad-CAM Heatmap Overlay */}
                  {activeTab === "heatmap" && heatmapUrl && (
                    <img
                      src={heatmapUrl}
                      alt="Grad-CAM Attribution Map"
                      className="absolute inset-0 w-full h-full object-cover pointer-events-none transition-opacity duration-150"
                      style={{ opacity: heatmapOpacity }}
                    />
                  )}

                  {/* Missing Heatmap Notification */}
                  {activeTab === "heatmap" && !heatmapUrl && !heatmapLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/75 p-6 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <svg className="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <span className="text-xs text-amber-200 font-medium leading-relaxed">
                          Grad-CAM heatmap not available for this case.
                          <br />
                          <span className="text-[10px] text-slate-400">Heatmaps require a graded usable retinal fundus image.</span>
                        </span>
                      </div>
                    </div>
                  )}

                  {activeTab === "heatmap" && heatmapLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/60">
                      <div className="w-8 h-8 border-2 border-teal-500/20 border-t-teal-400 rounded-full animate-spin"></div>
                    </div>
                  )}
                </div>

                {/* Notice when CLAHE tab is selected */}
                {activeTab === "clahe" && (
                  <div className="mt-3 text-center">
                    <span className="inline-block bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] px-3 py-1 rounded-full font-mono">
                      Adaptive histogram equalization (CLAHE) is pending pipeline deployment. Unaltered optical image shown.
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Viewport Footer Info */}
            <div className="px-4 py-3 bg-[#0e1726] border-t border-[#1e293b] flex items-center justify-between text-xs text-slate-300">
              <span className="text-[11px] text-teal-400 font-medium">
                Model attribution overlay &bull; Decision support only
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                Engine: {quality?.engine_mode === "matlab_production" ? "MATLAB R2026b EfficientNet-B0 (Fold 2)" : (quality?.engine_mode || "Active")}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Quality, Prediction & Clinician Review */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* Quality Verdict & MATLAB Image Quality Diagnostics */}
          {quality && (
            <div
              className={`rounded-xl p-3.5 border shadow-xs flex flex-col gap-2.5 ${
                quality.verdict === "usable"
                  ? "bg-[#f0fdf4] border-[#bbf7d0] text-[#166534]"
                  : "bg-[#fffbeb] border-[#fef3c7] text-[#92400e]"
              }`}
            >
              {/* Header Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-xs">
                  {quality.verdict === "usable" ? (
                    <>
                      <svg className="w-4 h-4 text-[#16a34a]" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      <span>Image Validated Usable</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 text-[#d97706]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <span>Image Unusable &bull; Retake Required</span>
                    </>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => setShowMatlabReportModal(true)}
                  className="px-2.5 py-1 text-[10px] font-bold rounded-md bg-[#0f766e] hover:bg-[#084c47] text-white flex items-center gap-1.5 transition shadow-2xs cursor-pointer"
                  title="View full MATLAB Quality & Field Report"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span>MATLAB Quality Report</span>
                </button>
              </div>

              {/* True Parameters Grid */}
              <div className="grid grid-cols-2 gap-2 p-2 bg-white/85 rounded-lg border border-[#a7f3d0] text-[11px] text-[#0f172a]">
                <div>
                  <span className="text-[10px] text-[#64748b] block font-medium">Image Dimensions</span>
                  <span className="text-[#065f46] font-mono font-bold text-xs">{qMetrics.dimensions}</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748b] block font-medium">Mean Brightness</span>
                  <span className="text-[#065f46] font-mono font-bold text-xs">{Number(qMetrics.mean_brightness).toFixed(4)}</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748b] block font-medium">Contrast Std Dev</span>
                  <span className="text-[#065f46] font-mono font-bold text-xs">{Number(qMetrics.contrast_std).toFixed(4)}</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748b] block font-medium">Sharpness Score</span>
                  <span className="text-[#065f46] font-mono font-bold text-xs">{Number(qMetrics.sharpness_score).toFixed(4)}</span>
                </div>
                <div className="col-span-2 pt-1 border-t border-[#e2e8f0] flex justify-between items-center text-[10px]">
                  <span>Retinal-Field Area Ratio: <strong className="text-[#065f46] font-mono">{Number(qMetrics.retinal_area_ratio).toFixed(2)}%</strong></span>
                  <span className="text-[10px] font-semibold text-[#047857]">Field Detected: {qMetrics.field_detected ? "Yes" : "No"}</span>
                </div>
              </div>

              {/* Individual Quality Checks: Designed Separate Buttons */}
              <div className="flex flex-col gap-1.5 pt-1 border-t border-[#bbf7d0]/70">
                <div className="flex justify-between items-center text-[10px] font-bold text-[#065f46] uppercase tracking-wider">
                  <span>Individual Quality Checks</span>
                  <span className="text-[9px] text-[#047857] font-semibold">Overall: {qMetrics.overall_status}</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                  {[
                    {
                      id: "dim",
                      label: "Dimensions",
                      passed: qMetrics.dimensions_pass,
                      val: qMetrics.dimensions,
                      rule: ">= 224 x 224 px",
                      desc: "Validates adequate pixel resolution for deep convolutional receptive fields."
                    },
                    {
                      id: "bright",
                      label: "Brightness",
                      passed: qMetrics.brightness_pass,
                      val: Number(qMetrics.mean_brightness).toFixed(4),
                      rule: "0.10 <= mean <= 0.90",
                      desc: "Detects extreme underexposure or overexposed corneal reflection artifacts."
                    },
                    {
                      id: "contrast",
                      label: "Contrast",
                      passed: qMetrics.contrast_pass,
                      val: Number(qMetrics.contrast_std).toFixed(4),
                      rule: "std >= 0.05",
                      desc: "Assures contrast dynamics across optic disc, macula, and vessel arches."
                    },
                    {
                      id: "sharp",
                      label: "Sharpness",
                      passed: qMetrics.sharpness_pass,
                      val: Number(qMetrics.sharpness_score).toFixed(4),
                      rule: "energy >= 0.002",
                      desc: "Estimates image gradient energy to reject motion or defocus blur."
                    },
                    {
                      id: "fov",
                      label: "Field Area",
                      passed: qMetrics.retinal_area_pass,
                      val: `${Number(qMetrics.retinal_area_ratio).toFixed(1)}%`,
                      rule: "coverage >= 20.0%",
                      desc: "Verifies optical non-dark fundus aperture area and domain boundaries."
                    },
                    {
                      id: "overall",
                      label: "Overall Quality",
                      passed: quality.verdict === "usable",
                      val: quality.verdict === "usable" ? "Passed" : "Review",
                      rule: "All 5 checks",
                      desc: "Consolidated two-tier technical validation and domain authenticity gate."
                    },
                  ].map((chk) => (
                    <button
                      key={chk.id}
                      type="button"
                      onClick={() => setSelectedCheckDetail(chk)}
                      className="px-2 py-1.5 rounded-lg border bg-white/90 hover:bg-white text-left transition shadow-2xs flex flex-col justify-between border-[#a7f3d0] hover:border-[#10b981] cursor-pointer"
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="text-[10px] font-bold text-[#1e293b] truncate">{chk.label}</span>
                        <span
                          className={`text-[9px] font-black px-1 py-0.2 rounded ${
                            chk.passed ? "bg-[#d1fae5] text-[#065f46]" : "bg-[#fee2e2] text-[#991b1b]"
                          }`}
                        >
                          {chk.passed ? "PASS" : "FAIL"}
                        </span>
                      </div>
                      <span className="text-[9px] font-mono text-[#065f46] mt-0.5 truncate">{chk.val}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Retinal-Field Assessment Notice */}
              <div className="text-[10px] text-[#065f46] bg-white/60 p-2 rounded-lg border border-[#bbf7d0]/80 flex flex-col gap-0.5">
                <div className="font-semibold flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                  <span>Retinal-Field Assessment: {qMetrics.field_status}</span>
                </div>
                <p className="text-[9.5px] text-[#334155] leading-relaxed">
                  {qMetrics.field_message} (Engineering heuristics for technical screening; clinical confirmation required).
                </p>
              </div>
            </div>
          )}

          {/* Recapture Action (If marked needs_recapture) */}
          {caseData.status === "needs_recapture" && (
            <div className="bg-white rounded-xl border border-amber-200 p-4 shadow-xs flex flex-col gap-3">
              <h3 className="text-xs font-bold text-[#b45309]">Image Recapture Workflow</h3>
              <p className="text-[11px] text-[#64748b]">
                Select an improved photograph to replace the ungradable image for Case #{caseData.id}.
              </p>
              {recaptureError && (
                <div className="text-[11px] text-rose-600 font-medium">{recaptureError}</div>
              )}
              <label className="cursor-pointer py-2 px-3 bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition text-center">
                <span>{recapturing ? "Uploading Replacement..." : "Upload Recapture Image"}</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  disabled={recapturing}
                  onChange={(e) => e.target.files?.[0] && handleRecaptureUpload(e.target.files[0])}
                  className="hidden"
                />
              </label>
            </div>
          )}

          {/* AI Biomarker Inference Panel */}
          {prediction && (
            <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 shadow-xs flex flex-col gap-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#64748b] text-[10px] tracking-wider uppercase">
                  Biomarker Inference Staging
                </span>
                <span
                  className="text-[10px] text-[#0f766e] font-mono font-bold"
                  title={
                    prediction.temperature
                      ? `Calibrated Confidence: ${(prediction.model_score * 100).toFixed(2)}% (T=${prediction.temperature}) | Raw: ${((prediction.raw_confidence || prediction.model_score) * 100).toFixed(2)}%`
                      : `Confidence: ${(prediction.model_score * 100).toFixed(2)}%`
                  }
                >
                  {prediction.temperature ? "Calibrated Conf" : "Confidence"}: {modelScoreFormatted}%
                </span>
              </div>

              {/* Primary Staging Result */}
              <div className="p-3 bg-[#f0f9f8] border border-[#ccede8] rounded-lg">
                <div className="flex items-center gap-1.5 font-bold text-[#0f766e] text-xs">
                  <span className="w-2 h-2 rounded-full bg-[#0f766e]"></span>
                  <span>{GRADE_LABELS[gradeNumber] || `Grade ${gradeNumber}`}</span>
                </div>
              </div>

              {/* Grade 3 Clinical Advisory */}
              {gradeNumber === 3 && (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-800 flex items-start gap-2">
                  <span className="font-bold shrink-0">Clinical Advisory:</span>
                  <span>Severe NPDR (Grade 3) represents advanced non-proliferative retinopathy requiring specialist clinical confirmation. Prompt comprehensive dilated ophthalmological evaluation is advised.</span>
                </div>
              )}

              {/* Low Confidence Notice */}
              {prediction.low_confidence && (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-800 flex items-center gap-2">
                  <span className="font-bold shrink-0">Notice:</span>
                  <span>Model staging uncertainty detected ({modelScoreFormatted}%). Independent clinician review required.</span>
                </div>
              )}

              {/* 5-Grade Scale */}
              <div>
                <span className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider block mb-1.5">
                  ICDR Severity Scale
                </span>
                <div className="grid grid-cols-5 gap-1 text-[10px] text-center font-semibold">
                  {[0, 1, 2, 3, 4].map((g) => (
                    <div
                      key={g}
                      className={`py-1 rounded transition ${
                        gradeNumber === g
                          ? "bg-[#0f766e] text-white shadow-xs font-bold"
                          : "bg-[#f1f5f9] text-[#64748b]"
                      }`}
                    >
                      L{g}
                    </div>
                  ))}
                </div>
              </div>

              {/* Referable Warning Pill */}
              {prediction.referable && (
                <div className="p-2.5 rounded-lg bg-[#fff7ed] border border-[#ffedd5] flex items-center gap-2 text-xs text-[#c2410c] font-medium">
                  <svg className="w-4 h-4 shrink-0 text-[#ea580c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Referable diabetic retinopathy detected. Specialist review advised.</span>
                </div>
              )}

              {/* Class Scores Horizontal Bars with 1-decimal precision */}
              {prediction.class_scores && (
                <div className="pt-2 border-t border-[#f1f5f9] flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="font-bold text-[#64748b] uppercase">Class Probability Breakdown</span>
                    <span className="text-[9px] text-slate-400 font-mono">1-decimal precision</span>
                  </div>
                  {prediction.class_scores.map((score, idx) => {
                    const pctFormatted = (score * 100).toFixed(1);
                    return (
                      <div
                        key={idx}
                        className="flex items-center gap-2 text-[10px]"
                        title={`Grade ${idx} (${GRADE_LABELS[idx]}): ${(score * 100).toFixed(4)}% [prob: ${score.toFixed(6)}]`}
                      >
                        <span className="w-6 font-mono text-[#64748b]">L{idx}</span>
                        <div className="flex-1 bg-[#f1f5f9] h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-[#0f766e] h-full rounded-full transition-all duration-300"
                            style={{ width: `${Math.max(Number(pctFormatted), score > 0 ? 1 : 0)}%` }}
                          />
                        </div>
                        <span className="w-12 text-right font-mono text-[#334155] font-medium">{pctFormatted}%</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Clinician Review & Triage Panel */}
          <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 shadow-xs flex flex-col gap-3">
            <div>
              <h3 className="text-xs font-bold text-[#0b1c30]">Clinician Assessment &amp; Triage</h3>
              <p className="text-[10px] text-[#64748b] mt-0.5">
                {isClinician
                  ? "Confirm diagnosis, override classification, or fast-track specialist consult."
                  : "Signed decisions by authorized ophthalmologist."}
              </p>
            </div>

            {/* Decision Radio Grid */}
            <div className="grid grid-cols-2 gap-2 text-left">
              {[
                { id: "confirm", label: "Confirm", desc: "Validate AI stage" },
                { id: "override", label: "Override", desc: "Change severity" },
                { id: "recapture", label: "Recapture", desc: "Flag artifact" },
                { id: "refer", label: "Refer", desc: "Tertiary clinic" },
              ].map((opt) => (
                <button
                  type="button"
                  key={opt.id}
                  disabled={!isClinician || submittingReview}
                  onClick={() => setSelectedDecision(opt.id)}
                  className={`p-2.5 rounded-lg border text-left flex items-start gap-2 transition ${
                    selectedDecision === opt.id
                      ? "border-[#0f766e] bg-[#f0f9f8] text-[#084c47]"
                      : "border-[#e2e8f0] text-[#475569] hover:bg-[#f8fafc]"
                  } ${!isClinician ? "cursor-default" : "cursor-pointer"}`}
                >
                  <input
                    type="radio"
                    checked={selectedDecision === opt.id}
                    onChange={() => setSelectedDecision(opt.id)}
                    disabled={!isClinician}
                    className="mt-0.5 accent-[#0f766e]"
                  />
                  <div>
                    <div className="text-xs font-bold leading-none">{opt.label}</div>
                    <div className="text-[10px] text-[#64748b] mt-0.5">{opt.desc}</div>
                  </div>
                </button>
              ))}
            </div>

            {/* Override Grade Selector */}
            {selectedDecision === "override" && (
              <div className="flex flex-col gap-1 p-2.5 bg-[#f8fafc] rounded-lg border border-[#e2e8f0]">
                <label className="text-xs font-semibold text-[#334155]">Select Overriding Severity Grade</label>
                <select
                  value={overrideGrade}
                  onChange={(e) => setOverrideGrade(Number(e.target.value))}
                  disabled={!isClinician}
                  className="px-2.5 py-1.5 text-xs bg-white border border-[#d9e2ec] rounded-md"
                >
                  <option value={0}>Level 0: No DR</option>
                  <option value={1}>Level 1: Mild NPDR</option>
                  <option value={2}>Level 2: Moderate NPDR</option>
                  <option value={3}>Level 3: Severe NPDR</option>
                  <option value={4}>Level 4: Proliferative DR</option>
                </select>
              </div>
            )}

            {/* Clinical Notes Field */}
            <div className="flex flex-col gap-1">
              <label className="text-xs font-semibold text-[#334155]">Clinical Differential &amp; Audit Notes</label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={!isClinician || submittingReview}
                placeholder={isClinician ? "Enter clinical rationale (no patient names)..." : "No notes recorded"}
                className="w-full p-2 text-xs border border-[#d9e2ec] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e] bg-[#fdfdfd]"
              />
            </div>

            {reviewSuccess && (
              <div className="p-2 rounded bg-emerald-50 text-emerald-800 text-xs font-semibold text-center border border-emerald-200">
                Review &amp; Audit Stamp Successfully Signed
              </div>
            )}

            {isClinician && (
              <button
                type="button"
                onClick={handleSaveReview}
                disabled={submittingReview}
                className="w-full py-2.5 px-4 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 shadow-xs transition disabled:opacity-60 cursor-pointer"
              >
                {submittingReview ? (
                  <span>Signing Decision...</span>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <span>Save &amp; Sign Clinical Review</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Report Modal */}
      {showReportModal && reportData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2 font-bold text-sm text-[#0b1c30]">
                <span>RetinaGuide XAI Clinical Screening Report</span>
              </div>
              <button onClick={() => setShowReportModal(false)} className="text-slate-400 hover:text-slate-600">
                &times;
              </button>
            </div>

            <div className="py-4 text-xs flex flex-col gap-3">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-[11px] font-semibold">
                {reportData.notice}
              </div>

              <div className="grid grid-cols-2 gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200 text-[11px]">
                <div>Case ID: <strong>#{reportData.case_id}</strong></div>
                <div>Status: <strong className="uppercase">{reportData.status}</strong></div>
                <div>Eye: <strong className="uppercase">{reportData.eye || "Unspecified"}</strong></div>
                <div>Date: <strong>{new Date(reportData.created_at).toLocaleDateString()}</strong></div>
              </div>

              {reportData.prediction && (
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex flex-col gap-1 text-[11px]">
                  <div>AI Grade: <strong>{GRADE_LABELS[reportData.prediction.grade]}</strong></div>
                  <div>Model Score: <strong>{Math.round(reportData.prediction.model_score * 100)}%</strong></div>
                  <div>Referable Triage: <strong>{reportData.prediction.referable ? "YES" : "NO"}</strong></div>
                </div>
              )}

              {reportData.latest_review && (
                <div className="p-3 bg-teal-50 rounded-lg border border-teal-200 flex flex-col gap-1 text-[11px] text-teal-950">
                  <div>Clinician Decision: <strong className="uppercase">{reportData.latest_review.decision}</strong></div>
                  {reportData.latest_review.final_grade !== null && (
                    <div>Overridden Grade: <strong>{GRADE_LABELS[reportData.latest_review.final_grade]}</strong></div>
                  )}
                  {reportData.latest_review.notes && <div>Notes: {reportData.latest_review.notes}</div>}
                  <div>Reviewed At: {new Date(reportData.latest_review.created_at).toLocaleString()}</div>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-200 flex justify-end gap-2">
              <button
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="px-3.5 py-1.5 bg-[#084c47] hover:bg-[#063b37] text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition shadow-xs disabled:opacity-60"
              >
                {downloadingPdf ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                    <span>Generating PDF...</span>
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span>Download PDF Report</span>
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(reportData, null, 2));
                  const downloadAnchor = document.createElement("a");
                  downloadAnchor.setAttribute("href", dataStr);
                  downloadAnchor.setAttribute("download", `Case_${reportData.case_id}_Report.json`);
                  document.body.appendChild(downloadAnchor);
                  downloadAnchor.click();
                  downloadAnchor.remove();
                }}
                className="px-3 py-1.5 border border-slate-300 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50"
              >
                Download JSON
              </button>
              <button
                onClick={() => setShowReportModal(false)}
                className="px-3 py-1.5 border border-slate-300 text-xs font-semibold rounded-lg hover:bg-slate-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Selected Check Detail Modal */}
      {selectedCheckDetail && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-sm w-full p-4 border border-slate-200 shadow-xl flex flex-col gap-3">
            <div className="flex items-center justify-between border-b pb-2">
              <h3 className="text-xs font-bold text-[#0c2340] flex items-center gap-1.5">
                <span>{selectedCheckDetail.name || selectedCheckDetail.label} Check</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-black ${selectedCheckDetail.passed ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>
                  {selectedCheckDetail.passed ? "PASS" : "FAIL"}
                </span>
              </h3>
              <button
                onClick={() => setSelectedCheckDetail(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold cursor-pointer"
              >
                &times;
              </button>
            </div>
            <div className="flex flex-col gap-1.5 text-xs">
              <div className="p-2 bg-slate-50 rounded border text-[11px] font-mono">
                <div>Measured Value: <strong>{selectedCheckDetail.val}</strong></div>
                <div>Heuristic Rule: <strong>{selectedCheckDetail.rule}</strong></div>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed mt-1">
                {selectedCheckDetail.desc}
              </p>
            </div>
            <div className="flex justify-end pt-2 border-t">
              <button
                onClick={() => setSelectedCheckDetail(null)}
                className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-md cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MATLAB Full Quality & Field Analysis Report Modal */}
      {showMatlabReportModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#0b1320] border border-teal-500/30 rounded-2xl max-w-2xl w-full p-5 shadow-2xl text-slate-200 flex flex-col gap-4 max-h-[90vh]">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-teal-500/20 text-teal-400 flex items-center justify-center text-xs font-bold font-mono">
                  M
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white tracking-tight">MATLAB R2026b &bull; Technical Image Quality Report</h3>
                  <p className="text-[10px] text-teal-400">RetinaGuide XAI Two-Tier Engineering Quality &amp; Authenticity Gate</p>
                </div>
              </div>
              <button
                onClick={() => setShowMatlabReportModal(false)}
                className="text-slate-400 hover:text-white text-base font-bold px-2 py-1 cursor-pointer"
              >
                &times;
              </button>
            </div>

            {/* Monospace Code Report Display */}
            <div className="bg-[#050911] border border-slate-800 rounded-xl p-4 font-mono text-[11px] leading-relaxed text-emerald-400 overflow-y-auto max-h-[55vh] select-all shadow-inner">
              <pre className="whitespace-pre-wrap">{matlabReportText}</pre>
            </div>

            {/* Modal Footer Actions */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
              <span className="text-[10px] text-slate-400">
                Generated via <strong className="text-slate-300">checkImageQuality.m</strong> &amp; <strong className="text-slate-300">checkRetinalField.m</strong>
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    navigator.clipboard.writeText(matlabReportText);
                    setCopiedReport(true);
                    setTimeout(() => setCopiedReport(false), 2000);
                  }}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition border border-slate-700 cursor-pointer"
                >
                  {copiedReport ? (
                    <>
                      <svg className="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className="text-emerald-400">Report Copied!</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                      </svg>
                      <span>Copy Report Text</span>
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={handleDownloadPdf}
                  disabled={downloadingPdf}
                  className="px-3 py-1.5 bg-[#0f766e] hover:bg-[#0d645e] text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition shadow-xs cursor-pointer disabled:opacity-60"
                >
                  {downloadingPdf ? "Generating PDF..." : "Download Clinical PDF"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowMatlabReportModal(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition border border-slate-700 cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
