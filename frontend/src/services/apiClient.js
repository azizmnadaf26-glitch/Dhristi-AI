/**
 * RetinaGuide XAI Centralized API Client
 *
 * Handles HTTP requests, JWT token attachment, HttpOnly refresh cookie rotation,
 * concurrency queueing for token refreshes, unified error parsing, and blob creation.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

let accessToken = null;
let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshed(token) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback) {
  refreshSubscribers.push(callback);
}

export function setAccessToken(token) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export function clearAccessToken() {
  accessToken = null;
}

/**
 * Custom application error with backend error metadata
 */
export class ApiError extends Error {
  constructor(status, code, message, details = null, requestId = null) {
    super(message || "An unexpected error occurred");
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

/**
 * Core fetch wrapper with token injection, refresh queue, and error formatting
 */
export async function apiRequest(endpoint, options = {}, isRetry = false) {
  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;
  const headers = { ...(options.headers || {}) };

  // Attach Authorization header if access token exists
  if (accessToken && !headers.Authorization) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  // Set Content-Type to JSON if sending object and not FormData
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const fetchOptions = {
    ...options,
    headers,
    credentials: "include", // Required for HttpOnly refresh cookie
  };

  let response;
  try {
    response = await fetch(url, fetchOptions);
  } catch (err) {
    throw new ApiError(0, "network_error", "Cannot connect to the server. Please check your connection or verify backend status.");
  }

  // Handle 401 Unauthorized for token refresh
  if (response.status === 401 && !isRetry && !endpoint.includes("/api/auth/login") && !endpoint.includes("/api/auth/refresh")) {
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        addRefreshSubscriber((newToken) => {
          if (!newToken) {
            return reject(new ApiError(401, "unauthorized", "Session expired. Please log in again."));
          }
          options.headers = {
            ...(options.headers || {}),
            Authorization: `Bearer ${newToken}`,
          };
          resolve(apiRequest(endpoint, options, true));
        });
      });
    }

    isRefreshing = true;

    try {
      const refreshResponse = await fetch(`${BASE_URL}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });

      if (refreshResponse.ok) {
        const refreshData = await refreshResponse.json();
        accessToken = refreshData.access_token;
        isRefreshing = false;
        onRefreshed(accessToken);

        // Retry original request with new token
        options.headers = {
          ...(options.headers || {}),
          Authorization: `Bearer ${accessToken}`,
        };
        return apiRequest(endpoint, options, true);
      } else {
        accessToken = null;
        isRefreshing = false;
        onRefreshed(null);
        window.dispatchEvent(new CustomEvent("auth_unauthorized"));
        throw new ApiError(401, "session_expired", "Session expired. Please log in again.");
      }
    } catch (refreshErr) {
      accessToken = null;
      isRefreshing = false;
      onRefreshed(null);
      window.dispatchEvent(new CustomEvent("auth_unauthorized"));
      throw refreshErr;
    }
  }

  // 204 No Content
  if (response.status === 204) {
    return null;
  }

  // Handle errors
  if (!response.ok) {
    let errorPayload = null;
    try {
      errorPayload = await response.json();
    } catch {
      // not JSON
    }

    const errorObj = errorPayload?.error || {};
    const code = errorObj.code || `http_${response.status}`;
    const message = errorObj.message || response.statusText || "Request failed";
    const details = errorObj.details || null;
    const requestId = errorObj.request_id || response.headers.get("X-Request-ID");

    throw new ApiError(response.status, code, message, details, requestId);
  }

  // Return parsed JSON or blob depending on request
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return await response.json();
  }
  return response;
}

// ==========================================
// Specialized Domain APIs
// ==========================================

export const authApi = {
  async login(email, password) {
    const data = await apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    return data;
  },

  async refresh() {
    const data = await apiRequest("/api/auth/refresh", {
      method: "POST",
    });
    setAccessToken(data.access_token);
    return data;
  },

  async logout() {
    try {
      await apiRequest("/api/auth/logout", {
        method: "POST",
      });
    } finally {
      clearAccessToken();
    }
  },

  async getMe() {
    return await apiRequest("/api/me");
  },

  async changePassword(current_password, new_password) {
    return await apiRequest("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    });
  },
};

export const configApi = {
  async getConfig() {
    return await apiRequest("/api/config");
  },

  async checkHealth() {
    const res = await fetch(`${BASE_URL}/api/health`);
    if (!res.ok) throw new Error("Health check failed");
    return await res.json();
  },
};

export const casesApi = {
  async uploadCase(file, patientRef = null, eye = null) {
    const formData = new FormData();
    formData.append("file", file);
    if (patientRef) formData.append("patient_ref", patientRef);
    if (eye && (eye === "left" || eye === "right")) formData.append("eye", eye);

    return await apiRequest("/api/cases", {
      method: "POST",
      body: formData,
    });
  },

  async listCases(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", params.page);
    if (params.page_size) query.set("page_size", params.page_size);
    if (params.status) query.set("status", params.status);

    const qs = query.toString();
    return await apiRequest(`/api/cases${qs ? `?${qs}` : ""}`);
  },

  async getCase(caseId) {
    return await apiRequest(`/api/cases/${caseId}`);
  },

  async requestReview(caseId) {
    return await apiRequest(`/api/cases/${caseId}/request-review`, {
      method: "POST",
    });
  },

  async reviewCase(caseId, { decision, final_grade = null, notes = null }) {
    return await apiRequest(`/api/cases/${caseId}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, final_grade, notes }),
    });
  },

  async recaptureCase(caseId, file) {
    const formData = new FormData();
    formData.append("file", file);

    return await apiRequest(`/api/cases/${caseId}/recapture`, {
      method: "POST",
      body: formData,
    });
  },

  async getReport(caseId) {
    return await apiRequest(`/api/cases/${caseId}/report`);
  },

  async downloadPdfReport(caseId) {
    const response = await apiRequest(`/api/cases/${caseId}/report.pdf`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `RetinaGuide_Report_Case_${caseId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 15000);
    return true;
  },

  async fetchImageBlobUrl(imageId) {
    const response = await apiRequest(`/api/images/${imageId}/file`);
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  async fetchHeatmapBlobUrl(imageId) {
    const response = await apiRequest(`/api/images/${imageId}/heatmap`);
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },
};

export const summaryApi = {
  async getSummary(dateFrom = null, dateTo = null) {
    const query = new URLSearchParams();
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    const qs = query.toString();
    return await apiRequest(`/api/summary${qs ? `?${qs}` : ""}`);
  },
};

export const evaluationApi = {
  async getLatest() {
    return await apiRequest("/api/evaluation/latest");
  },

  async getRuns(params = {}) {
    const query = new URLSearchParams();
    if (params.split) query.set("split", params.split);
    if (params.page) query.set("page", params.page);
    if (params.page_size) query.set("page_size", params.page_size);
    const qs = query.toString();
    return await apiRequest(`/api/evaluation/runs${qs ? `?${qs}` : ""}`);
  },
};

export const simulationApi = {
  async startSimulation(params) {
    return await apiRequest("/api/simulations", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async listSimulations(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", params.page);
    if (params.page_size) query.set("page_size", params.page_size);
    const qs = query.toString();
    return await apiRequest(`/api/simulations${qs ? `?${qs}` : ""}`);
  },

  async getSimulation(id) {
    return await apiRequest(`/api/simulations/${id}`);
  },
};

export const adminApi = {
  async listUsers(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", params.page);
    if (params.page_size) query.set("page_size", params.page_size);
    if (params.role) query.set("role", params.role);
    if (params.is_active !== undefined && params.is_active !== null) {
      query.set("is_active", params.is_active);
    }
    const qs = query.toString();
    return await apiRequest(`/api/admin/users${qs ? `?${qs}` : ""}`);
  },

  async createUser({ email, role }) {
    return await apiRequest("/api/admin/users", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
  },

  async updateUser(userId, { role = null, is_active = null }) {
    const body = {};
    if (role !== null) body.role = role;
    if (is_active !== null) body.is_active = is_active;
    return await apiRequest(`/api/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  async resetPassword(userId) {
    return await apiRequest(`/api/admin/users/${userId}/reset-password`, {
      method: "POST",
    });
  },

  async listAudit(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", params.page);
    if (params.page_size) query.set("page_size", params.page_size);
    if (params.action) query.set("action", params.action);
    if (params.outcome) query.set("outcome", params.outcome);
    if (params.actor_id) query.set("actor_id", params.actor_id);
    const qs = query.toString();
    return await apiRequest(`/api/admin/audit${qs ? `?${qs}` : ""}`);
  },

  async listModels(params = {}) {
    const query = new URLSearchParams();
    if (params.page) query.set("page", params.page);
    if (params.page_size) query.set("page_size", params.page_size);
    const qs = query.toString();
    return await apiRequest(`/api/admin/models${qs ? `?${qs}` : ""}`);
  },
};
