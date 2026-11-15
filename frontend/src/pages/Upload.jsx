import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, CheckCircle2, Activity, Cpu, Sparkles, Check } from "lucide-react";
import { casesApi } from "@/services/apiClient";

const PIPELINE_STEPS = [
  {
    step: 1,
    title: "Ingesting Retinal Photograph",
    desc: "Validating file dimensions, payload size & DICOM/PNG metadata",
  },
  {
    step: 2,
    title: "MATLAB R2026b Optical Diagnostics",
    desc: "Measuring mean brightness, contrast standard deviation, sharpness & retinal aperture",
  },
  {
    step: 3,
    title: "EfficientNet-B0 Deep Learning Inference",
    desc: "Staging ICDR biomarkers across 5 severity classes with temperature scaling",
  },
  {
    step: 4,
    title: "Layer-243 Grad-CAM Explainability",
    desc: "Synthesizing gradient-weighted class activation attribution overlay",
  },
  {
    step: 5,
    title: "Compiling Case Evaluation Report",
    desc: "Assembling doctor-shareable report & telemetry payload",
  },
];

const clinicalSamples = [
  {
    id: "PK-4012",
    title: "Normal Fundus - Baseline",
    badge: "Verified Clean Quality",
    badgeType: "success",
    format: "2048x1536 PNG • 4.2 MB",
    modality: "Digital Retinal Camera",
    fov: "45° FOV",
    image: "/retinal/fundus-3.png",
    eye: "right",
  },
  {
    id: "PK-3189",
    title: "Mild NPDR / Microaneurysms",
    badge: "Triage Priority",
    badgeType: "warning",
    format: "2160x1800 PNG • 3.8 MB",
    modality: "Digital Retinal Camera",
    fov: "50° FOV",
    image: "/retinal/fundus-1.png",
    eye: "left",
  },
  {
    id: "PK-8821",
    title: "Suspected Glaucoma / CDR = 0.7",
    badge: "Triage Priority",
    badgeType: "warning",
    format: "2048x1536 PNG • 4.8 MB",
    modality: "Digital Retinal Camera",
    fov: "Disc Focus",
    image: "/retinal/fundus-2.png",
    eye: "right",
  },
  {
    id: "PK-4410",
    title: "Macular Edema Risk",
    badge: "High Quality Scan",
    badgeType: "success",
    format: "3000x2000 JPEG • 6.1 MB",
    modality: "Digital Retinal Camera",
    fov: "45° FOV",
    image: "/retinal/fundus-4.png",
    eye: "left",
  },
];

export default function Upload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [patientRef, setPatientRef] = useState("");
  const [eye, setEye] = useState("right");
  const [uploading, setUploading] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);
  const [pipelineProgress, setPipelineProgress] = useState(0);
  const [loadingSample, setLoadingSample] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const handleFileSelect = (file) => {
    setErrorMessage("");
    if (!file) return;

    if (!["image/jpeg", "image/png"].includes(file.type)) {
      setErrorMessage("Unsupported image format. Only JPEG and PNG images are accepted.");
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      setErrorMessage("File exceeds 15 MB limit. Please select an optimized fundus image.");
      return;
    }

    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleLoadSample = async (sample) => {
    setLoadingSample(sample.id);
    setErrorMessage("");
    try {
      const response = await fetch(sample.image);
      const blob = await response.blob();
      const ext = sample.image.endsWith(".png") ? "png" : "jpg";
      const file = new File([blob], `${sample.id}_fundus.${ext}`, { type: blob.type || "image/png" });

      setPatientRef(sample.id);
      setEye(sample.eye || "right");
      handleFileSelect(file);
    } catch (err) {
      setErrorMessage("Could not load sample image asset.");
    } finally {
      setLoadingSample(null);
    }
  };

  const handleUploadSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!selectedFile) {
      setErrorMessage("Please select a retinal photograph before submitting.");
      return;
    }

    setUploading(true);
    setPipelineStage(0);
    setPipelineProgress(15);
    setErrorMessage("");

    try {
      const cleanRef = patientRef.trim() || undefined;
      const cleanEye = eye === "left" || eye === "right" ? eye : undefined;

      // 1. Submit upload payload
      const response = await casesApi.uploadCase(selectedFile, cleanRef, cleanEye);
      const caseId = response.id;

      // Stage 1: Optical Quality
      setPipelineStage(1);
      setPipelineProgress(35);

      // Smooth timed stage progression
      const t1 = setTimeout(() => {
        setPipelineStage(2);
        setPipelineProgress(65);
      }, 700);

      const t2 = setTimeout(() => {
        setPipelineStage(3);
        setPipelineProgress(85);
      }, 1400);

      // Poll until backend completes inference
      const startTime = Date.now();
      let completed = false;
      while (!completed && Date.now() - startTime < 8000) {
        await new Promise((r) => setTimeout(r, 500));
        try {
          const check = await casesApi.getCase(caseId);
          if (check.status !== "uploaded") {
            completed = true;
          }
        } catch {
          // ignore transient poll error
        }
      }

      clearTimeout(t1);
      clearTimeout(t2);

      // Stage 4: Synthesizing Report
      setPipelineStage(4);
      setPipelineProgress(100);

      await new Promise((r) => setTimeout(r, 450));
      navigate(`/cases/${caseId}`);
    } catch (err) {
      setErrorMessage(err.message || "Failed to upload retinal photograph.");
      setUploading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full">
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
        accept="image/jpeg,image/png"
        className="hidden"
      />

      <div>
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#f0f9f8] text-[#0f766e] text-[10px] font-bold tracking-wider uppercase mb-1">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span>Retinal Ingestion Gateway</span>
        </div>
        <h1 className="text-xl font-bold text-[#0b1c30] tracking-tight">Upload retinal image</h1>
        <p className="text-xs text-[#64748b] mt-0.5">
          Upload a high-resolution fundus photograph for clinical quality assessment and diabetic retinopathy staging.
        </p>
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

      {/* Upload Drop Zone & Selected Preview */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] p-6 shadow-xs">
        {!selectedFile ? (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl py-10 px-6 flex flex-col items-center justify-center text-center transition cursor-pointer ${
              dragActive ? "border-[#0f766e] bg-[#f0f9f8]/60" : "border-[#cbd5e1] hover:border-[#0f766e]/70"
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="w-14 h-14 rounded-full bg-[#eff6ff] text-[#3b82f6] flex items-center justify-center mb-3">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>

            <h3 className="text-sm font-bold text-[#0b1c30]">
              Drag a retinal photograph here or click to browse
            </h3>
            <span className="text-xs text-[#94a3b8] mt-1">JPEG or PNG &bull; Max 15 MB &bull; Strips EXIF PHI</span>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="mt-4 px-4 py-2 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-xs transition cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              <span>Browse Local Files</span>
            </button>
          </div>
        ) : (
          <div className="flex flex-col md:flex-row gap-6 items-center">
            <div className="relative w-44 h-44 rounded-xl overflow-hidden border-2 border-[#1e293b] shadow-md bg-black shrink-0 flex items-center justify-center">
              <img src={previewUrl} alt="Retinal Preview" className="w-full h-full object-cover" />
              <button
                type="button"
                onClick={() => {
                  setSelectedFile(null);
                  setPreviewUrl(null);
                }}
                className="absolute top-2 right-2 p-1 bg-black/70 hover:bg-black text-white rounded-full transition"
                title="Remove image"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex flex-col gap-3 flex-1 w-full">
              <div>
                <h3 className="text-sm font-bold text-[#0b1c30] truncate">{selectedFile.name}</h3>
                <div className="text-xs text-[#64748b] mt-0.5">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB &bull; {selectedFile.type}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-[#334155] mb-1">
                    Patient Reference (Optional)
                  </label>
                  <input
                    type="text"
                    value={patientRef}
                    onChange={(e) => setPatientRef(e.target.value)}
                    placeholder="e.g. PT-4012"
                    maxLength={100}
                    disabled={uploading}
                    className="w-full px-3 py-2 text-xs border border-[#d9e2ec] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#334155] mb-1">
                    Eye Designation
                  </label>
                  <select
                    value={eye}
                    onChange={(e) => setEye(e.target.value)}
                    disabled={uploading}
                    className="w-full px-3 py-2 text-xs border border-[#d9e2ec] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e]"
                  >
                    <option value="right">OD (Right Eye)</option>
                    <option value="left">OS (Left Eye)</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3 mt-3">
                <button
                  type="button"
                  onClick={handleUploadSubmit}
                  disabled={uploading}
                  className="px-5 py-2.5 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-xs transition disabled:opacity-75 cursor-pointer"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-white" />
                      <span>Generating Data &amp; Staging...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      <span>Submit for Inference</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="px-3.5 py-2.5 border border-[#d8e3ed] hover:bg-[#f8fafc] text-[#475569] rounded-lg text-xs font-semibold transition"
                >
                  Change File
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Benchmark Cohort Pre-Loaded Clinical Reference Samples */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-[#0b1c30]">
            Or select a pre-loaded clinical reference sample
          </h2>
          <span className="text-[10px] text-[#94a3b8] font-mono">Benchmark Cohort v1.3</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {clinicalSamples.map((sample) => (
            <div key={sample.id} className="bg-white rounded-xl border border-[#e2e8f0] p-4 flex flex-col justify-between shadow-xs hover:border-[#cbd5e1] transition">
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  {sample.badgeType === "success" ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#15803d]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a]"></span>
                      {sample.badge}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#b45309]">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b]"></span>
                      {sample.badge}
                    </span>
                  )}

                  <svg className="w-3.5 h-3.5 text-[#94a3b8]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>

                <div className="relative w-full h-36 bg-[#0c121e] rounded-lg overflow-hidden flex items-center justify-center border border-[#1e293b]">
                  <img src={sample.image} alt={sample.title} className="w-28 h-28 object-cover rounded-full shadow-lg" />
                  <span className="absolute bottom-2 right-2 bg-black/70 text-white text-[9px] font-mono px-1.5 py-0.5 rounded border border-white/20">
                    {sample.fov}
                  </span>
                </div>

                <div className="mt-3">
                  <h3 className="text-xs font-bold text-[#0b1c30]">{sample.title}</h3>
                  <div className="text-[10px] text-[#0f766e] font-semibold mt-0.5">
                    Sample Ref: {sample.id} &bull; Eye: {sample.eye.toUpperCase()}
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-[#64748b] mt-2 pt-2 border-t border-[#f1f5f9]">
                    <span>Format: {sample.format}</span>
                    <span>{sample.modality}</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleLoadSample(sample)}
                disabled={loadingSample === sample.id || uploading}
                className="w-full mt-3 py-1.5 px-3 bg-[#f0f9f8] hover:bg-[#e1f3f0] text-[#0f766e] border border-[#ccede8] rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                <span>{loadingSample === sample.id ? "Loading Sample..." : "Use Reference Sample"}</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Real-time Clinical Data Generation Loading Overlay */}
      {uploading && (
        <div className="fixed inset-0 z-50 bg-[#0b1c30]/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-[#e2e8f0] p-6 max-w-lg w-full flex flex-col gap-5 text-center animate-in fade-in zoom-in-95 duration-200">
            {/* Glowing Processing Animation */}
            <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-4 border-[#ccfbf1] opacity-75"></div>
              <div className="absolute inset-0 rounded-full border-4 border-t-[#0f766e] border-r-transparent border-b-[#0f766e] border-l-transparent animate-spin"></div>
              <div className="w-12 h-12 rounded-full bg-[#f0fdfa] flex items-center justify-center text-[#0f766e] shadow-inner">
                <Cpu className="w-6 h-6 animate-pulse" />
              </div>
            </div>

            {/* Header */}
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#f0fdfa] border border-[#ccfbf1] text-[#0f766e] text-[10px] font-bold tracking-wider uppercase mb-1">
                <Sparkles className="w-3 h-3 text-[#0f766e]" />
                <span>Live AI Inference Engine Active</span>
              </div>
              <h3 className="text-lg font-black text-[#0b1c30] tracking-tight">
                Generating Clinical Inference &amp; Diagnostics
              </h3>
              <p className="text-xs text-[#64748b] mt-0.5">
                MATLAB R2026b &bull; EfficientNet-B0 ONNX &bull; Grad-CAM Layer 243
              </p>
            </div>

            {/* Progress Bar */}
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between text-[11px] font-bold">
                <span className="text-[#0f766e]">
                  {PIPELINE_STEPS[pipelineStage]?.title || "Processing..."}
                </span>
                <span className="font-mono text-[#0b1c30]">{pipelineProgress}%</span>
              </div>
              <div className="w-full h-2.5 bg-[#f1f5f9] rounded-full overflow-hidden p-0.5 border border-[#e2e8f0]">
                <div
                  className="h-full bg-linear-to-r from-[#0f766e] via-[#0d9488] to-[#14b8a6] rounded-full transition-all duration-300"
                  style={{ width: `${pipelineProgress}%` }}
                ></div>
              </div>
            </div>

            {/* Pipeline Stage Tracker */}
            <div className="bg-[#f8fafc] border border-[#e2e8f0] rounded-xl p-3 flex flex-col gap-2.5 text-left">
              {PIPELINE_STEPS.map((s, idx) => {
                const isPassed = pipelineStage > idx;
                const isCurrent = pipelineStage === idx;
                return (
                  <div key={s.step} className="flex items-start gap-2.5">
                    <div className="mt-0.5 shrink-0">
                      {isPassed ? (
                        <CheckCircle2 className="w-4 h-4 text-[#10b981]" />
                      ) : isCurrent ? (
                        <Loader2 className="w-4 h-4 text-[#0f766e] animate-spin" />
                      ) : (
                        <div className="w-4 h-4 rounded-full border border-[#cbd5e1] flex items-center justify-center text-[9px] font-mono text-[#94a3b8]">
                          {s.step}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span
                        className={`text-xs font-bold ${
                          isPassed
                            ? "text-[#059669]"
                            : isCurrent
                            ? "text-[#0f766e]"
                            : "text-[#94a3b8]"
                        }`}
                      >
                        {s.title}
                      </span>
                      <span className="text-[10px] text-[#64748b] leading-tight">
                        {s.desc}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Telemetry pill */}
            <div className="text-[10px] text-[#64748b] font-mono flex items-center justify-center gap-2 pt-1 border-t border-[#f1f5f9]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping"></span>
              <span>Node c5.4xlarge &bull; Temperature T=2.7600 &bull; Fold 2 ONNX</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
