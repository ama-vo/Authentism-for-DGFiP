// Onglet "Journaux" : les 200 derniers événements, filtrables par priorité
import { useEffect, useState } from "react";
import { api } from "../../api";
import { LogEntry } from "../../types";
import { useAdminError } from "./useAdminError";

export default function LogsTab() {
  const { error, handleError } = useAdminError();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [priority, setPriority] = useState("");

  async function load() {
    try {
      const query = priority ? `?priority=${priority}` : "";
      const data = await api<{ logs: LogEntry[] }>(`/admin/logs${query}`);
      setLogs(data.logs);
    } catch (err) {
      handleError(err);
    }
  }

  useEffect(() => {
    load();
  }, [priority]);

  return (
    <>
      {error && <p className="alert error">{error}</p>}

      <div className="toolbar">
        <label htmlFor="priority">Priorité :</label>
        <select id="priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">Toutes</option>
          <option value="CRITIQUE">Critique</option>
          <option value="ELEVE">Élevée</option>
          <option value="INFO">Info</option>
        </select>
        <button className="btn btn-secondary" onClick={load}>Actualiser</button>
      </div>

      <div className="table-wrap">
        <table className="logs">
          <thead>
            <tr><th>Date (UTC)</th><th>Priorité</th><th>Compte</th><th>Action</th><th>Endpoint</th><th>IP</th><th>Détails</th></tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className={log.success ? "" : "failed"}>
                <td>{new Date(log.timestamp).toISOString().replace("T", " ").slice(0, 19)}</td>
                <td><span className={`prio prio-${log.priority}`}>{log.priority}</span></td>
                <td>{log.account}</td>
                <td>{log.success ? "✓" : "✗"} {log.action}</td>
                <td><code>{log.endpoint}</code></td>
                <td>{log.ip}</td>
                <td>{log.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
