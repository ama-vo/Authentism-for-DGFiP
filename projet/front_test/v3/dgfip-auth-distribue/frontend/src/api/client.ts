// Le front ne parle QU'à l'Application Web (webapp). Il ignore tout
// du Système d'authentification et du Collecteur de logs, qui ne
// sont pas exposés au navigateur — conformément au schéma.
//
// En développement (`npm run dev`), VITE_API_URL pointe directement
// vers webapp (ex. http://localhost:5000), CORS géré côté Flask.
// En production (conteneur Docker), l'appel passe par le même
// nom d'hôte que le site : Nginx reçoit /api/* et le relaie en
// interne vers webapp — le navigateur ne voit jamais l'adresse du
// backend, un seul point d'entrée public existe.
const API_URL = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
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
  // Flux 1 : POST /login.php
  login: (fiscal_id: string, password: string) =>
    request<{ pending_token: string; expires_in_seconds: number; debug_code?: string }>(
      "/login.php",
      { method: "POST", body: { fiscal_id, password } }
    ),

  // Flux 5/6 : validation du code 2FA
  verifyMfa: (pending_token: string, code: string) =>
    request<{ token: string; role: string; fiscal_id: string; redirect: string }>(
      "/login.php/verify",
      { method: "POST", body: { pending_token, code } }
    ),

  resendMfa: (pending_token: string) =>
    request<{ expires_in_seconds: number; debug_code?: string }>(
      "/login.php/resend",
      { method: "POST", body: { pending_token } }
    ),

  logout: (token: string) => request<{ ok: true }>("/logout", { method: "POST", token }),

  // Flux 6/7/8/9 : tableau de bord + liste des endpoints accessibles
  dashboard: (token: string) =>
    request<{ fiscal_id: string; role: string; links: import("../types").DashboardLink[] }>(
      "/dashboard.php",
      { token }
    ),

  // Flux 9 : « tout autre endpoint », exemple générique
  page1: (token: string) =>
    request<{ page: string; content: string }>("/page1.php", { token }),

  // Flux 10/11 : échange du jeton de session contre un jeton admin scopé
  getAdminToken: (token: string) =>
    request<{ admin_token: string; expires_in_seconds: number; scoped_endpoint: string }>(
      "/admin.php/token",
      { method: "POST", token }
    ),

  adminHome: (adminToken: string) =>
    request<{ fiscal_id: string; message: string }>("/admin.php", { token: adminToken }),

  // Flux 12/13 : consultation du journal (événements admin priorisés)
  adminLogs: (adminToken: string) =>
    request<import("../types").LogEntry[]>("/admin.php/logs", { token: adminToken }),
};
