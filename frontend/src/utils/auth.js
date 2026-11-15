/**
 * RetinaGuide XAI Authentication & Session Service
 *
 * Backed by real FastAPI authentication (/api/auth/login, /api/auth/refresh, /api/me).
 * Roles and permissions are verified server-side.
 */

import { authApi, clearAccessToken, setAccessToken } from "@/services/apiClient";

const SESSION_CACHE_KEY = "retinaguide_user_cache";

export const ROLE_CONFIG = {
  operator: {
    role: "operator",
    title: "Clinical Imaging Tech",
    defaultRoute: "/upload",
    allowedRoutes: ["/upload", "/", "/cases", "/cases/:id", "/evaluation"],
  },
  clinician: {
    role: "clinician",
    title: "Attending Ophthalmologist",
    defaultRoute: "/cases",
    allowedRoutes: ["/upload", "/", "/cases", "/cases/:id", "/evaluation"],
  },
  planner: {
    role: "planner",
    title: "Healthcare Operations Planner",
    defaultRoute: "/summary",
    allowedRoutes: ["/summary", "/simulation"],
  },
  admin: {
    role: "admin",
    title: "System Administrator",
    defaultRoute: "/admin/users",
    allowedRoutes: ["/admin/users", "/admin/audit", "/admin/models"],
  },
};

let currentUser = null;
let sessionCheckPromise = null;

// Populate initial cache if present
try {
  const cached = sessionStorage.getItem(SESSION_CACHE_KEY);
  if (cached) {
    currentUser = JSON.parse(cached);
  }
} catch {
  currentUser = null;
}

function saveUserCache(user) {
  currentUser = user;
  if (user) {
    try {
      sessionStorage.setItem(SESSION_CACHE_KEY, JSON.stringify(user));
    } catch {
      // ignore
    }
  } else {
    try {
      sessionStorage.removeItem(SESSION_CACHE_KEY);
    } catch {
      // ignore
    }
  }
  window.dispatchEvent(new Event("auth_change"));
}

// Auto handle unauthorized broadcast
if (typeof window !== "undefined") {
  window.addEventListener("auth_unauthorized", () => {
    saveUserCache(null);
  });
}

function computeDisplayName(email, role) {
  if (!email) return "Clinical User";
  const prefix = email.split("@")[0].replace(/[._]/g, " ");
  const capitalized = prefix
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
  return role === "clinician" ? `Dr. ${capitalized}` : capitalized;
}

function computeInitials(displayName) {
  if (!displayName) return "RG";
  const parts = displayName.replace(/^Dr\.\s*/i, "").trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return parts[0].slice(0, 2).toUpperCase();
}

function enrichUserData(backendUser) {
  if (!backendUser) return null;
  const role = (backendUser.role || "operator").toLowerCase();
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.operator;
  const name = computeDisplayName(backendUser.email, role);
  const initials = computeInitials(name);

  return {
    id: backendUser.id,
    email: backendUser.email,
    role,
    must_change_password: backendUser.must_change_password,
    name,
    title: config.title,
    initials,
    defaultRoute: config.defaultRoute,
    allowedRoutes: config.allowedRoutes,
  };
}

export const auth = {
  isAuthenticated() {
    return !!currentUser;
  },

  getUser() {
    return currentUser;
  },

  async login(email, password) {
    const tokenRes = await authApi.login(email, password);
    const meRes = await authApi.getMe();
    const enriched = enrichUserData(meRes);
    saveUserCache(enriched);
    return enriched;
  },

  async restoreSession() {
    if (sessionCheckPromise) return sessionCheckPromise;

    sessionCheckPromise = (async () => {
      try {
        await authApi.refresh();
        const meRes = await authApi.getMe();
        const enriched = enrichUserData(meRes);
        saveUserCache(enriched);
        return enriched;
      } catch (err) {
        saveUserCache(null);
        clearAccessToken();
        return null;
      } finally {
        sessionCheckPromise = null;
      }
    })();

    return sessionCheckPromise;
  },

  async logout() {
    try {
      await authApi.logout();
    } finally {
      saveUserCache(null);
      clearAccessToken();
    }
  },

  getDefaultRoute(role) {
    const roleKey = (role || "").toLowerCase();
    return ROLE_CONFIG[roleKey]?.defaultRoute || "/upload";
  },

  isRouteAllowed(role, pathname) {
    const roleKey = (role || "operator").toLowerCase();
    const config = ROLE_CONFIG[roleKey];
    if (!config) return false;

    return config.allowedRoutes.some((pattern) => {
      if (pattern === pathname) return true;
      if (pattern === "/" && pathname === "/upload") return true;
      if (pattern === "/cases/:id" && pathname.startsWith("/cases/") && pathname !== "/cases") {
        return true;
      }
      return false;
    });
  },
};

// Backwards compatibility alias for components importing mockAuth
export const mockAuth = auth;

export const PRESET_ROLES = ROLE_CONFIG;

export const hasRole = (user, allowedRoles) => {
  if (!user) return false;
  const currentRole = String(user.role || "").toLowerCase();
  if (Array.isArray(allowedRoles)) {
    return allowedRoles.map((r) => r.toLowerCase()).includes(currentRole);
  }
  return currentRole === String(allowedRoles || "").toLowerCase();
};
