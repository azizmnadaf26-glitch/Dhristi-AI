import React, { useState, useEffect } from "react";
import { adminApi } from "@/services/apiClient";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("All");

  // Create User Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("operator");
  const [creating, setCreating] = useState(false);
  const [createSuccessData, setCreateSuccessData] = useState(null);

  // Reset Password Modal State
  const [resetModalData, setResetModalData] = useState(null);

  const fetchUsers = async () => {
    setLoading(true);
    setErrorMessage("");
    try {
      const params = {};
      if (roleFilter !== "All") {
        params.role = roleFilter;
      }
      const res = await adminApi.listUsers(params);
      setUsers(res.items || []);
    } catch (err) {
      setErrorMessage(err.message || "Failed to load system users.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [roleFilter]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setCreating(true);
    setErrorMessage("");
    try {
      const result = await adminApi.createUser({
        email: newEmail.trim().toLowerCase(),
        role: newRole,
      });
      setCreateSuccessData(result);
      fetchUsers();
    } catch (err) {
      setErrorMessage(err.message || "Failed to create user.");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (user) => {
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active });
      fetchUsers();
    } catch (err) {
      setErrorMessage(err.message || "Could not update user active status.");
    }
  };

  const handleResetPassword = async (user) => {
    try {
      const res = await adminApi.resetPassword(user.id);
      setResetModalData(res);
    } catch (err) {
      setErrorMessage(err.message || "Failed to reset password.");
    }
  };

  const filteredUsers = users.filter((u) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return u.email?.toLowerCase().includes(term) || u.role?.toLowerCase().includes(term);
  });

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-[#0b1c30] tracking-tight">User Account Directory</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#eff6ff] text-[#1e40af] border border-[#dbeafe]">
              FastAPI RBAC
            </span>
          </div>
          <p className="text-xs text-[#64748b] mt-0.5">
            Provision user roles, manage credentials, and audit authentication security across clinical staff.
          </p>
        </div>

        <button
          onClick={() => {
            setShowCreateModal(true);
            setCreateSuccessData(null);
            setNewEmail("");
          }}
          className="px-3.5 py-2 bg-[#084c47] hover:bg-[#063b37] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-xs transition w-fit cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
          </svg>
          <span>Provision New User</span>
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

      {/* Filters Bar */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] p-4 flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between shadow-xs">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search accounts by email or role..."
            className="w-full px-3 py-2 text-xs border border-[#d9e2ec] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 focus:border-[#0f766e]"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          {["All", "operator", "clinician", "planner", "admin"].map((r) => (
            <button
              key={r}
              onClick={() => setRoleFilter(r)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition cursor-pointer capitalize ${
                roleFilter === r ? "bg-[#084c47] text-white shadow-xs" : "bg-[#f1f5f9] text-[#475569] hover:bg-[#e2e8f0]"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-[#e2e8f0] shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-xs text-slate-500">Loading system accounts...</div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-500">No users found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#f8fafc] text-[#64748b] font-semibold border-b border-[#e2e8f0]">
                  <th className="py-3 px-4">User ID</th>
                  <th className="py-3 px-4">Clinical Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Account Status</th>
                  <th className="py-3 px-4">Password State</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f1f5f9]">
                {filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-[#f8fafc]/80 transition">
                    <td className="py-3 px-4 font-mono font-bold text-[#0f766e]">#{u.id}</td>
                    <td className="py-3 px-4 font-semibold text-[#0b1c30]">{u.email}</td>
                    <td className="py-3 px-4">
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase bg-slate-100 text-slate-800">
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                        u.is_active ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}>
                        {u.is_active ? "Active" : "Deactivated"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#64748b]">
                      {u.must_change_password ? (
                        <span className="text-amber-600 font-semibold text-[11px]">Must Change</span>
                      ) : (
                        <span className="text-emerald-600 text-[11px]">Verified</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleResetPassword(u)}
                          className="px-2.5 py-1 bg-white border border-[#d8e3ed] hover:bg-slate-50 text-slate-700 rounded text-[11px] font-semibold"
                        >
                          Reset Pass
                        </button>
                        <button
                          onClick={() => handleToggleActive(u)}
                          className={`px-2.5 py-1 rounded text-[11px] font-semibold ${
                            u.is_active ? "text-rose-600 hover:bg-rose-50" : "text-emerald-600 hover:bg-emerald-50"
                          }`}
                        >
                          {u.is_active ? "Deactivate" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Create User */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h2 className="text-sm font-bold text-[#0b1c30]">Provision Clinical User Account</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-600">
                &times;
              </button>
            </div>

            {createSuccessData ? (
              <div className="py-4 flex flex-col gap-3">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-900 text-xs">
                  <div className="font-bold text-sm mb-1">User Created Successfully!</div>
                  <div>Account: <strong>{createSuccessData.user.email}</strong></div>
                  <div>Role: <strong className="uppercase">{createSuccessData.user.role}</strong></div>
                </div>

                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs flex flex-col gap-1">
                  <span className="font-bold text-amber-900">One-Time Temporary Password:</span>
                  <div className="p-2 bg-white rounded border border-amber-300 font-mono text-sm font-bold text-[#0b1c30] select-all">
                    {createSuccessData.temp_password}
                  </div>
                  <span className="text-[10px] text-amber-700">
                    Provide this password to the clinician. By security policy, it is only displayed once and will not be shown again.
                  </span>
                </div>

                <button
                  onClick={() => setShowCreateModal(false)}
                  className="w-full mt-2 py-2 bg-[#084c47] text-white text-xs font-semibold rounded-lg"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleCreateUser} className="py-4 flex flex-col gap-3 text-xs">
                <div>
                  <label className="block font-semibold text-[#334155] mb-1">Email Address</label>
                  <input
                    type="email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    placeholder="doctor@hospital.org"
                    required
                    className="w-full px-3 py-2 border border-[#d9e2ec] rounded-lg"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-[#334155] mb-1">System Role</label>
                  <select
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value)}
                    className="w-full px-3 py-2 border border-[#d9e2ec] rounded-lg bg-white"
                  >
                    <option value="operator">Operator (Imaging Technician)</option>
                    <option value="clinician">Clinician (Ophthalmologist / MD)</option>
                    <option value="planner">Planner (Healthcare Operations)</option>
                    <option value="admin">System Administrator</option>
                  </select>
                </div>

                <div className="pt-3 border-t border-slate-200 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-3 py-1.5 border border-slate-300 rounded-lg text-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="px-4 py-1.5 bg-[#084c47] hover:bg-[#063b37] text-white font-semibold rounded-lg"
                  >
                    {creating ? "Provisioning..." : "Create Account"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Modal: Password Reset Show */}
      {resetModalData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200">
            <h2 className="text-sm font-bold text-[#0b1c30] mb-2">Temporary Password Reset</h2>
            <p className="text-xs text-[#64748b] mb-3">
              Password for <strong>{resetModalData.user.email}</strong> was reset.
            </p>
            <div className="p-3 bg-slate-100 rounded-lg font-mono text-sm font-bold text-center select-all border border-slate-300 mb-4">
              {resetModalData.temp_password}
            </div>
            <button
              onClick={() => setResetModalData(null)}
              className="w-full py-2 bg-[#084c47] text-white text-xs font-semibold rounded-lg"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
