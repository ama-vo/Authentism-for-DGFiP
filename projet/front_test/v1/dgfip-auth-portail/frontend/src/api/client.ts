const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:5000/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  token?: string | null;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;

  const res = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;

  if (!res.ok) {
    const message = (data && (data.error as string)) || "Une erreur est survenue.";
    throw new ApiError(message, res.status);
  }
  return data as T;
}

export const api = {
  login: (fiscal_id: string, password: string) =>
    request<{ pending_token: string; expires_in_seconds: number; debug_code?: string }>(
      "/auth/login",
      { method: "POST", body: { fiscal_id, password } }
    ),

  verifyMfa: (pending_token: string, code: string) =>
    request<{ token: string; role: string; fiscal_id: string; name: string }>(
      "/auth/mfa/verify",
      { method: "POST", body: { pending_token, code } }
    ),

  resendMfa: (pending_token: string) =>
    request<{ expires_in_seconds: number; debug_code?: string }>(
      "/auth/mfa/resend",
      { method: "POST", body: { pending_token } }
    ),

  logout: (token: string) =>
    request<{ ok: true }>("/auth/logout", { method: "POST", token }),

  listServices: (token: string) =>
    request<Array<{ id: string; name: string; allowed: boolean }>>("/services", { token }),

  accessService: (token: string, serviceId: string) =>
    request<{ ok: true; service: string }>(`/services/${serviceId}/access`, {
      method: "POST",
      token,
    }),

  getAdminToken: (token: string, password: string) =>
    request<{ admin_token: string; expires_in_seconds: number }>("/admin/token", {
      method: "POST",
      token,
      body: { password },
    }),

  listAccounts: (adminToken: string) =>
    request<import("../types").Account[]>("/admin/accounts", { token: adminToken }),

  createAccount: (
    adminToken: string,
    payload: { fiscal_id: string; name: string; role: string; password: string }
  ) =>
    request<import("../types").Account>("/admin/accounts", {
      method: "POST",
      token: adminToken,
      body: payload,
    }),

  updateAccount: (adminToken: string, id: number, payload: { name?: string; role?: string }) =>
    request<import("../types").Account>(`/admin/accounts/${id}`, {
      method: "PUT",
      token: adminToken,
      body: payload,
    }),

  deleteAccount: (adminToken: string, id: number) =>
    request<{ ok: true }>(`/admin/accounts/${id}`, { method: "DELETE", token: adminToken }),

  listLogs: (adminToken: string) =>
    request<import("../types").LogEntry[]>("/admin/logs", { token: adminToken }),
};
