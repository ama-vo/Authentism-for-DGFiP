// Le front ne parle QU'à l'Application Web, via /api (relayé par Nginx en
// production, par Vite en développement). Les jetons de session sont dans
// des cookies HttpOnly : le JavaScript ne les voit jamais.
import type {
  ChallengeResponse,
  DashboardLink,
  LogEntry,
  ManagedPage,
  ManagedUser,
  Priority,
  SessionUser,
  StandardPage,
} from "../types";

const API = "/api";

export class ApiError extends Error {
  status: number;
  data: Record<string, unknown>;
  constructor(message: string, status: number, data: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        // En-tête anti-CSRF exigé par webapp sur toute requête non-GET.
        "X-Requested-With": "fetch",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Impossible de contacter le serveur.", 0, {});
  }
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : {};
  if (!res.ok) {
    const message =
      (data && typeof data.error === "string" && data.error) ||
      (res.status === 429 ? "Trop de requêtes, réessayez dans un instant." : "Une erreur est survenue.");
    throw new ApiError(message, res.status, data ?? {});
  }
  return data as T;
}

export function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : "Une erreur inattendue est survenue.";
}

export const api = {
  // Flux 1 → 4
  login: (fiscal_id: string, password: string) =>
    request<ChallengeResponse>("POST", "/login.php", { fiscal_id, password }),
  // Flux 5/6
  verifyMfa: (challenge_token: string, code: string) =>
    request<SessionUser & { redirect: string }>("POST", "/login.php/verify", { challenge_token, code }),
  resendMfa: (challenge_token: string) =>
    request<ChallengeResponse>("POST", "/login.php/resend", { challenge_token }),

  forgotPassword: (fiscal_id: string) => request<ChallengeResponse>("POST", "/password/forgot", { fiscal_id }),
  resendReset: (challenge_token: string) =>
    request<ChallengeResponse>("POST", "/password/resend", { challenge_token }),
  resetPassword: (challenge_token: string, code: string, new_password: string) =>
    request<{ ok: true }>("POST", "/password/reset", { challenge_token, code, new_password }),

  session: () => request<SessionUser & { expires_in: number }>("GET", "/session"),
  logout: () => request<{ ok: true }>("POST", "/logout"),

  // Flux 6 → 9
  dashboard: () =>
    request<{ fiscal_id: string; name: string; role: string; links: DashboardLink[] }>("GET", "/dashboard.php"),
  page: (slug: string) => request<StandardPage>("GET", `/${encodeURIComponent(slug)}.php`),

  // Flux 10/11
  adminToken: (password: string) =>
    request<{ expires_in: number; scoped_endpoint: string }>("POST", "/admin.php/token", { password }),
  adminHome: () => request<{ fiscal_id: string; name: string; expires_in: number }>("GET", "/admin.php"),
  adminLeave: () => request<{ ok: true }>("POST", "/admin.php/logout"),

  users: () => request<ManagedUser[]>("GET", "/admin.php/users"),
  createUser: (u: { fiscal_id: string; name: string; email: string; role: string; password: string }) =>
    request<{ ok: true }>("POST", "/admin.php/users", u),
  updateUser: (fiscalId: string, changes: { name?: string; email?: string; role?: string; unlock?: boolean }) =>
    request<{ ok: true }>("PATCH", `/admin.php/users/${fiscalId}`, changes),
  setUserPassword: (fiscalId: string, new_password: string) =>
    request<{ ok: true }>("POST", `/admin.php/users/${fiscalId}/password`, { new_password }),
  deleteUser: (fiscalId: string) => request<{ ok: true }>("DELETE", `/admin.php/users/${fiscalId}`),

  pages: () => request<ManagedPage[]>("GET", "/admin.php/pages"),
  createPage: (p: ManagedPage) => request<ManagedPage>("POST", "/admin.php/pages", p),
  updatePage: (p: ManagedPage) => request<ManagedPage>("PUT", `/admin.php/pages/${p.slug}`, p),
  deletePage: (slug: string) => request<{ ok: true }>("DELETE", `/admin.php/pages/${slug}`),

  // Flux 12/13
  logs: (params: { priority?: Priority | ""; order?: "priority" | "time"; account?: string }) => {
    const q = new URLSearchParams({ limit: "300" });
    if (params.priority) q.set("priority", params.priority);
    if (params.order) q.set("order", params.order);
    if (params.account) q.set("account", params.account);
    return request<LogEntry[]>("GET", `/admin.php/logs?${q.toString()}`);
  },
  verifyLogs: () =>
    request<{ valid: boolean; count: number; first_invalid_line?: number }>("GET", "/admin.php/logs/verify"),
};
