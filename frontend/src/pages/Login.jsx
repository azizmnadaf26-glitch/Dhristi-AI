import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { auth } from "@/utils/auth";

const QUICK_CREDS = {
  clinician: { email: "clinician@example.com", password: "Clinician1234!" },
  planner: { email: "planner@example.com", password: "Planner1234!" },
  admin: { email: "admin@example.com", password: "AdminPass1234!" },
};

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();

  const [selectedRole, setSelectedRole] = useState("clinician");
  const [email, setEmail] = useState("clinician@example.com");
  const [password, setPassword] = useState("Clinician1234!");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleRoleChange = (roleKey) => {
    setSelectedRole(roleKey);
    setErrorMessage("");
    const cred = QUICK_CREDS[roleKey];
    if (cred) {
      setEmail(cred.email);
      setPassword(cred.password);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");
    setLoading(true);

    try {
      const user = await auth.login(email.trim(), password);

      // Determine destination route
      const params = new URLSearchParams(location.search);
      const from = params.get("from");
      const destination = from ? decodeURIComponent(from) : user.defaultRoute || "/upload";

      navigate(destination, { replace: true });
    } catch (err) {
      setErrorMessage(err.message || "Failed to authenticate. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#f4f7fb] flex flex-col justify-center items-center px-4 py-8 relative">
      <div className="absolute inset-0 bg-radial from-white/90 via-[#f3f7fc] to-[#eaf0f8] pointer-events-none" />

      <div className="relative z-10 w-full max-w-[440px] bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.06)] border border-[#e8edf5] px-7 py-8">
        {/* Brand Icon */}
        <div className="flex justify-center mb-4">
          <div className="relative w-20 h-20 rounded-full bg-[#f0f9f8] border border-[#d1ebe7] flex items-center justify-center p-2 shadow-xs">
            <svg viewBox="0 0 100 100" className="w-full h-full text-[#0f766e]" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="50" cy="50" r="44" stroke="#a7d9d3" strokeWidth="1.5" strokeDasharray="4 3" />
              <path d="M32 25 H25 V32 M68 25 H75 V32 M25 68 V75 H32 M75 68 V75 H68" stroke="#2dd4bf" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="12" y1="50" x2="22" y2="50" stroke="#99f6e4" strokeWidth="1.5" />
              <line x1="78" y1="50" x2="88" y2="50" stroke="#99f6e4" strokeWidth="1.5" />
              <path d="M20 50 C30 35, 70 35, 80 50 C70 65, 30 65, 20 50 Z" stroke="#0f766e" strokeWidth="2" fill="#ffffff" />
              <circle cx="50" cy="50" r="14" fill="#0f766e" />
              <circle cx="50" cy="50" r="10" fill="#044e47" />
              <circle cx="50" cy="50" r="5" fill="#022c27" />
              <circle cx="48" cy="48" r="2" fill="#ffffff" />
            </svg>
          </div>
        </div>

        <div className="text-center mb-5">
          <h1 className="text-xl font-bold text-[#0c2340] tracking-tight">Clinical Sign In</h1>
          <p className="text-xs text-[#6b7c93] mt-1 font-medium">Medical Decision Support System</p>
        </div>

        {/* Quick Credential Role Fillers */}
        <div className="mb-4">
          <div className="flex justify-between items-center text-xs mb-1.5">
            <label className="font-semibold text-[#334155]">Quick-Fill Clinical Account</label>
            <span className="text-[#94a3b8] text-[11px]">Backend RBAC</span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 p-1 bg-[#f1f5f9] rounded-lg border border-[#e2e8f0]">
            {[
              { id: "clinician", label: "Clinician" },
              { id: "planner", label: "Planner" },
              { id: "admin", label: "Admin" },
            ].map((role) => (
              <button
                type="button"
                key={role.id}
                onClick={() => handleRoleChange(role.id)}
                className={`py-1.5 text-[11px] font-semibold rounded-md transition duration-150 ${
                  selectedRole === role.id
                    ? "bg-[#0f766e] text-white shadow-xs"
                    : "text-[#64748b] hover:text-[#0f172a] hover:bg-white/60"
                }`}
              >
                {role.label}
              </button>
            ))}
          </div>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
            <svg className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="leading-tight font-medium">{errorMessage}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center text-xs">
              <label className="font-semibold text-[#334155]">Clinical Email or ID</label>
              <span className="text-[#94a3b8] text-[11px] font-medium">NPI / Org Auth</span>
            </div>
            <div className="relative flex items-center">
              <span className="absolute left-3 text-[#94a3b8] flex items-center pointer-events-none">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@clinic.system"
                required
                disabled={loading}
                className="w-full pl-9 pr-3 py-2 text-xs text-[#0f172a] placeholder-[#94a3b8] bg-[#fdfdfd] border border-[#d9e2ec] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e] transition"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center text-xs">
              <label className="font-semibold text-[#334155]">Password</label>
              <span className="text-[#64748b] text-[11px]">Min 10 characters</span>
            </div>
            <div className="relative flex items-center">
              <span className="absolute left-3 text-[#94a3b8] flex items-center pointer-events-none">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </span>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                required
                disabled={loading}
                className="w-full pl-9 pr-9 py-2 text-xs text-[#0f172a] placeholder-[#94a3b8] bg-[#fdfdfd] border border-[#d9e2ec] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e] transition"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 text-[#94a3b8] hover:text-[#475569] transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  {showPassword ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  )}
                </svg>
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-0.5">
            <input
              id="remember"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-4 h-4 rounded text-[#0f766e] accent-[#0f766e] border-[#cbd5e1] focus:ring-[#0f766e] cursor-pointer"
            />
            <label htmlFor="remember" className="text-xs font-medium text-[#475569] cursor-pointer select-none">
              Remember clinical workstation
            </label>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 px-4 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 shadow-xs transition duration-150 disabled:opacity-60 cursor-pointer"
          >
            {loading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                <span>Authorizing Session...</span>
              </>
            ) : (
              <>
                <span>Sign In via FastAPI Authenticator</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </>
            )}
          </button>
        </form>
      </div>

      <div className="relative z-10 max-w-[420px] text-center mt-6 flex flex-col items-center gap-1.5 text-[11px] text-[#64748b]">
        <div className="flex items-center gap-1.5 font-semibold text-[#334155]">
          <svg className="w-3.5 h-3.5 text-[#0f766e]" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <span>HIPAA Compliant &amp; 256-Bit TLS Encrypted</span>
        </div>
        <p className="leading-relaxed text-[#7c8ba1] text-[10px]">
          Authorized use only. All diagnostic interactions and patient data queries are audited under FHIR standard protocols.
        </p>
      </div>
    </div>
  );
}
