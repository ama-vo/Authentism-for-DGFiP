// Petite fonction pour appeler l'API.
// Les cookies de session sont HttpOnly : le JavaScript ne les voit jamais,
// le navigateur les envoie tout seul à chaque requête.

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function api<T = unknown>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    // Session expirée pendant la navigation : retour à la page de connexion
    if (response.status === 401 && data.code === "NOT_AUTHENTICATED") {
      window.location.href = "/connexion?expire=1";
    }
    // 429 / 503 : file d'attente de nginx pleine (forte affluence)
    if (response.status === 429 || response.status === 503) {
      throw new ApiError(data.error || "Le service est très sollicité. Merci de patienter quelques instants.", response.status);
    }
    throw new ApiError(data.error || "Une erreur est survenue", response.status, data.code);
  }

  return data as T;
}

// Renvoie un message d'erreur lisible, quelle que soit l'erreur attrapée
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Une erreur est survenue";
}
