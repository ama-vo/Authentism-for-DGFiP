import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { LogEntry } from "../types";

export function AdminPage() {
  const { adminToken } = useAuth();
  const [message, setMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!adminToken) return;
    api
      .adminHome(adminToken)
      .then((res) => setMessage(res.message))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur de chargement."));
    api
      .adminLogs(adminToken)
      .then(setLogs)
      .catch(() => setLogs([]));
  }, [adminToken]);

  return (
    <div>
      <div className="portal-head">
        <h1>Panneau d'administration</h1>
        <p>{message ?? "Jeton d'administration scopé actif — accès limité à /admin.php."}</p>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="panel">
        <div className="panel-head">
          <h2>Journal de traçabilité</h2>
          <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>
            Événements de session administrateur en priorité (flux 13)
          </span>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Horodatage (UTC)</th>
                <th>Source</th>
                <th>Compte</th>
                <th>Action</th>
                <th>Endpoint</th>
                <th>IP</th>
                <th>Priorité</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l, i) => (
                <tr key={i}>
                  <td className="mono">{l.timestamp}</td>
                  <td className="mono">{l.source}</td>
                  <td className="mono">{l.account}</td>
                  <td>{l.action}</td>
                  <td className="mono">{l.endpoint}</td>
                  <td className="mono">{l.ip}</td>
                  <td>
                    <span className={`badge prio-${l.priority}`}>
                      {l.priority === "high" ? "Élevée" : "Normale"}
                    </span>
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-state">
                    Aucun événement enregistré.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
