import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, ApiError, errorMessage } from "../api/client";
import { PasswordChecklist } from "../components/PasswordChecklist";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS, type LogEntry, type ManagedPage, type ManagedUser, type Priority, type Role } from "../types";
import { isFiscalIdValid, isPasswordValid } from "../utils/validation";

type Tab = "users" | "pages" | "logs";
const ROLES: Role[] = ["external", "agent", "admin"];

// Toute erreur 403 « jeton admin » renvoie vers la page d'échange.
function useAdminGuard() {
  const navigate = useNavigate();
  return useCallback(
    (err: unknown, setError: (m: string) => void) => {
      if (err instanceof ApiError && (err.status === 403 || err.status === 401) && err.data.admin_token_required !== false) {
        if (err.status === 401) navigate("/login", { replace: true, state: { notice: "Votre session a expiré." } });
        else navigate("/admin/acces", { replace: true });
        return;
      }
      setError(errorMessage(err));
    },
    [navigate]
  );
}

export function AdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const guard = useAdminGuard();
  const [tab, setTab] = useState<Tab>("users");
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .adminHome()
      .then((res) => setExpiresAt(Date.now() + res.expires_in * 1000))
      .catch((err) => guard(err, setError));
  }, [guard]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  if (user && user.role !== "admin") return <Navigate to="/dashboard" replace />;

  const remaining = expiresAt ? Math.max(0, Math.round((expiresAt - now) / 1000)) : null;

  async function leave() {
    try {
      await api.adminLeave();
    } finally {
      navigate("/dashboard");
    }
  }

  return (
    <div>
      <div className="portal-head admin-head">
        <div>
          <h1>Panneau d'administration</h1>
          <p>Jeton administrateur scopé à /admin.php — toutes les actions sont journalisées en priorité critique.</p>
        </div>
        <div className="admin-timer">
          {remaining !== null && (
            <span className={remaining < 60 ? "danger" : ""}>
              Jeton valable encore {Math.floor(remaining / 60)} min {String(remaining % 60).padStart(2, "0")} s
            </span>
          )}
          <button type="button" className="btn-logout" onClick={leave}>
            Quitter l'administration
          </button>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <nav className="tabs" role="tablist">
        {(
          [
            ["users", "Comptes"],
            ["pages", "Pages du tableau de bord"],
            ["logs", "Journal de traçabilité"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key}
            className={tab === key ? "tab active" : "tab"} onClick={() => setTab(key)}>
            {label}
          </button>
        ))}
      </nav>

      {tab === "users" && <UsersPanel guard={guard} selfId={user?.fiscal_id ?? ""} />}
      {tab === "pages" && <PagesPanel guard={guard} />}
      {tab === "logs" && <LogsPanel guard={guard} />}
    </div>
  );
}

type Guard = ReturnType<typeof useAdminGuard>;

// ---------------------------------------------------------------------
// Comptes : créer, modifier les accès, changer le mot de passe, supprimer
// ---------------------------------------------------------------------
function UsersPanel({ guard, selfId }: { guard: Guard; selfId: string }) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [pwFor, setPwFor] = useState<string | null>(null);
  const [deleteFor, setDeleteFor] = useState<string | null>(null);

  const load = useCallback(() => {
    api.users().then(setUsers).catch((err) => guard(err, setError));
  }, [guard]);

  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      load();
      return true;
    } catch (err) {
      guard(err, setError);
      return false;
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Comptes ({users.length})</h2>
        <button type="button" className="btn-small" onClick={() => setShowCreate((s) => !s)}>
          {showCreate ? "Annuler" : "+ Créer un compte"}
        </button>
      </div>

      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert success">{notice}</div>}

      {showCreate && (
        <CreateUserForm
          onCreate={async (u) => {
            const ok = await run(() => api.createUser(u), `Compte ${u.fiscal_id} créé.`);
            if (ok) setShowCreate(false);
          }}
        />
      )}

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Numéro fiscal</th>
              <th>Nom</th>
              <th>E-mail</th>
              <th>Rôle (accès)</th>
              <th>État</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const self = u.fiscal_id === selfId;
              return (
                <tr key={u.fiscal_id}>
                  <td className="mono">{u.fiscal_id}</td>
                  <td>{u.name}{self && <span className="muted"> (vous)</span>}</td>
                  <td className="mono small">{u.email}</td>
                  <td>
                    <select
                      value={u.role ?? ""}
                      disabled={self}
                      aria-label={`Rôle de ${u.fiscal_id}`}
                      onChange={(e) =>
                        run(() => api.updateUser(u.fiscal_id, { role: e.target.value }),
                          `Accès de ${u.fiscal_id} modifiés : ${ROLE_LABELS[e.target.value as Role]}. Ses sessions ont été révoquées.`)
                      }
                    >
                      {!u.role && <option value="">— aucun —</option>}
                      {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                  </td>
                  <td className="small">
                    {u.locked ? <span className="badge prio-critical">Verrouillé</span> : <span className="badge ok">Actif</span>}
                    <div className="muted">{u.active_sessions} session(s)</div>
                  </td>
                  <td className="actions">
                    {u.locked && (
                      <button type="button" className="btn-link"
                        onClick={() => run(() => api.updateUser(u.fiscal_id, { unlock: true }), `Compte ${u.fiscal_id} déverrouillé.`)}>
                        Déverrouiller
                      </button>
                    )}
                    <button type="button" className="btn-link" onClick={() => { setPwFor(u.fiscal_id); setDeleteFor(null); }}>
                      Mot de passe
                    </button>
                    {!self && (
                      <button type="button" className="btn-link danger" onClick={() => { setDeleteFor(u.fiscal_id); setPwFor(null); }}>
                        Supprimer
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pwFor && (
        <SetPasswordForm
          fiscalId={pwFor}
          onCancel={() => setPwFor(null)}
          onSubmit={async (pw) => {
            const ok = await run(() => api.setUserPassword(pwFor, pw),
              `Mot de passe de ${pwFor} modifié. Ses sessions ont été révoquées.`);
            if (ok) setPwFor(null);
          }}
        />
      )}

      {deleteFor && (
        <div className="confirm-box">
          <p>
            Supprimer définitivement le compte <strong className="mono">{deleteFor}</strong> ? Ses sessions seront
            révoquées et il sera retiré de l'annuaire LDAP.
          </p>
          <div className="row">
            <button type="button" className="btn-danger"
              onClick={async () => {
                const id = deleteFor;
                setDeleteFor(null);
                await run(() => api.deleteUser(id), `Compte ${id} supprimé.`);
              }}>
              Confirmer la suppression
            </button>
            <button type="button" className="btn-small" onClick={() => setDeleteFor(null)}>Annuler</button>
          </div>
        </div>
      )}
    </div>
  );
}

function CreateUserForm({
  onCreate,
}: {
  onCreate: (u: { fiscal_id: string; name: string; email: string; role: string; password: string }) => Promise<void>;
}) {
  const [form, setForm] = useState({ fiscal_id: "", name: "", email: "", role: "external", password: "" });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!isFiscalIdValid(form.fiscal_id)) return setError("Numéro fiscal : 13 chiffres.");
    if (!form.name.trim()) return setError("Nom requis.");
    if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(form.email)) return setError("Adresse e-mail invalide.");
    if (!isPasswordValid(form.password)) return setError("Le mot de passe ne respecte pas la politique de sécurité.");
    await onCreate(form);
  }

  return (
    <form className="subform" onSubmit={submit} noValidate>
      {error && <div className="alert error">{error}</div>}
      <div className="form-grid">
        <div className="field">
          <label htmlFor="nf">Numéro fiscal</label>
          <input id="nf" type="text" inputMode="numeric" maxLength={13} value={form.fiscal_id}
            onChange={(e) => set("fiscal_id")(e.target.value.replace(/\D/g, "").slice(0, 13))} />
        </div>
        <div className="field">
          <label htmlFor="nn">Nom complet</label>
          <input id="nn" type="text" maxLength={64} value={form.name} onChange={(e) => set("name")(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="ne">E-mail (reçoit les codes 2FA)</label>
          <input id="ne" type="email" maxLength={254} value={form.email} onChange={(e) => set("email")(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="nr">Rôle</label>
          <select id="nr" value={form.role} onChange={(e) => set("role")(e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor="np">Mot de passe initial</label>
        <input id="np" type="password" autoComplete="new-password" maxLength={128} value={form.password}
          onChange={(e) => set("password")(e.target.value)} />
        <PasswordChecklist password={form.password} />
      </div>
      <button type="submit" className="btn-primary inline">Créer le compte</button>
    </form>
  );
}

function SetPasswordForm({
  fiscalId,
  onSubmit,
  onCancel,
}: {
  fiscalId: string;
  onSubmit: (pw: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [pw, setPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="confirm-box"
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        if (!isPasswordValid(pw)) return setError("Le mot de passe ne respecte pas la politique de sécurité.");
        await onSubmit(pw);
      }}
    >
      <p>
        Nouveau mot de passe pour <strong className="mono">{fiscalId}</strong>
      </p>
      {error && <div className="alert error">{error}</div>}
      <input type="password" autoComplete="new-password" maxLength={128} value={pw}
        aria-label="Nouveau mot de passe" onChange={(e) => setPw(e.target.value)} autoFocus />
      <PasswordChecklist password={pw} />
      <div className="row spaced">
        <button type="submit" className="btn-danger">Enregistrer</button>
        <button type="button" className="btn-small" onClick={onCancel}>Annuler</button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------
// Pages du tableau de bord (whitelist dynamique)
// ---------------------------------------------------------------------
const EMPTY_PAGE: ManagedPage = { slug: "", label: "", description: "", content: "", roles: ["admin"], visible: true };

function PagesPanel({ guard }: { guard: Guard }) {
  const [pages, setPages] = useState<ManagedPage[]>([]);
  const [editing, setEditing] = useState<{ page: ManagedPage; isNew: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    api.pages().then(setPages).catch((err) => guard(err, setError));
  }, [guard]);
  useEffect(load, [load]);

  async function save(page: ManagedPage, isNew: boolean) {
    setError(null);
    setNotice(null);
    try {
      await (isNew ? api.createPage(page) : api.updatePage(page));
      setNotice(`Page /${page.slug}.php enregistrée.`);
      setEditing(null);
      load();
    } catch (err) {
      guard(err, setError);
    }
  }

  async function remove(slug: string) {
    setError(null);
    try {
      await api.deletePage(slug);
      setNotice(`Page /${slug}.php supprimée.`);
      setEditing(null);
      load();
    } catch (err) {
      guard(err, setError);
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Pages du tableau de bord</h2>
        <button type="button" className="btn-small" onClick={() => setEditing({ page: EMPTY_PAGE, isNew: true })}>
          + Nouvelle page
        </button>
      </div>
      <p className="muted small">
        Chaque page est un endpoint <span className="mono">/&lt;identifiant&gt;.php</span> de la liste d'autorisation :
        seuls les rôles cochés y accèdent, toute autre tentative est refusée et journalisée.
      </p>
      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert success">{notice}</div>}

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>Libellé</th>
              <th>Rôles autorisés</th>
              <th>Visible</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.slug}>
                <td className="mono">/{p.slug}.php</td>
                <td>{p.label}</td>
                <td>{p.roles.map((r) => ROLE_LABELS[r]).join(", ")}</td>
                <td>{p.visible ? "Oui" : "Non"}</td>
                <td className="actions">
                  <button type="button" className="btn-link" onClick={() => setEditing({ page: p, isNew: false })}>
                    Modifier
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <PageEditor
          key={editing.page.slug || "new"}
          initial={editing.page}
          isNew={editing.isNew}
          onSave={save}
          onDelete={remove}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function PageEditor({
  initial,
  isNew,
  onSave,
  onDelete,
  onCancel,
}: {
  initial: ManagedPage;
  isNew: boolean;
  onSave: (p: ManagedPage, isNew: boolean) => Promise<void>;
  onDelete: (slug: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [page, setPage] = useState(initial);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const toggleRole = (r: Role) =>
    setPage((p) => ({ ...p, roles: p.roles.includes(r) ? p.roles.filter((x) => x !== r) : [...p.roles, r] }));

  return (
    <form className="subform" noValidate onSubmit={(e) => { e.preventDefault(); void onSave(page, isNew); }}>
      <h3>{isNew ? "Nouvelle page" : `Modifier /${page.slug}.php`}</h3>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="ps">Identifiant (URL)</label>
          <input id="ps" type="text" maxLength={32} disabled={!isNew} value={page.slug}
            onChange={(e) => setPage({ ...page, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} />
        </div>
        <div className="field">
          <label htmlFor="pl">Libellé</label>
          <input id="pl" type="text" maxLength={80} value={page.label} onChange={(e) => setPage({ ...page, label: e.target.value })} />
        </div>
      </div>
      <div className="field">
        <label htmlFor="pd">Description (tuile du tableau de bord)</label>
        <input id="pd" type="text" maxLength={200} value={page.description}
          onChange={(e) => setPage({ ...page, description: e.target.value })} />
      </div>
      <div className="field">
        <label htmlFor="pc">Contenu</label>
        <textarea id="pc" maxLength={2000} rows={3} value={page.content}
          onChange={(e) => setPage({ ...page, content: e.target.value })} />
      </div>
      <fieldset className="field roles-fieldset">
        <legend>Rôles autorisés</legend>
        {ROLES.map((r) => (
          <label key={r} className="check">
            <input type="checkbox" checked={page.roles.includes(r)} onChange={() => toggleRole(r)} /> {ROLE_LABELS[r]}
          </label>
        ))}
        <label className="check">
          <input type="checkbox" checked={page.visible} onChange={(e) => setPage({ ...page, visible: e.target.checked })} />{" "}
          Afficher sur le tableau de bord
        </label>
      </fieldset>
      <div className="row">
        <button type="submit" className="btn-primary inline">Enregistrer</button>
        <button type="button" className="btn-small" onClick={onCancel}>Annuler</button>
        {!isNew && !confirmDelete && (
          <button type="button" className="btn-link danger" onClick={() => setConfirmDelete(true)}>Supprimer la page</button>
        )}
        {!isNew && confirmDelete && (
          <button type="button" className="btn-danger" onClick={() => void onDelete(page.slug)}>Confirmer la suppression</button>
        )}
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------
// Journal de traçabilité (flux 12/13)
// ---------------------------------------------------------------------
const PRIORITY_LABELS: Record<Priority, string> = { critical: "Critique", high: "Élevée", normal: "Normale" };

function LogsPanel({ guard }: { guard: Guard }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [priority, setPriority] = useState<Priority | "">("");
  const [order, setOrder] = useState<"priority" | "time">("priority");
  const [account, setAccount] = useState("");
  const [integrity, setIntegrity] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .logs({ priority, order, account: isFiscalIdValid(account) ? account : undefined })
      .then(setLogs)
      .catch((err) => guard(err, setError));
  }, [priority, order, account, guard]);
  useEffect(load, [load]);

  async function verify() {
    try {
      const res = await api.verifyLogs();
      setIntegrity(
        res.valid
          ? `Chaîne d'intégrité valide (${res.count} événements, aucune altération).`
          : `ALTÉRATION DÉTECTÉE à la ligne ${res.first_invalid_line} sur ${res.count}.`
      );
    } catch (err) {
      guard(err, setError);
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Journal de traçabilité</h2>
        <div className="row">
          <select value={priority} onChange={(e) => setPriority(e.target.value as Priority | "")} aria-label="Priorité">
            <option value="">Toutes priorités</option>
            <option value="critical">Critique</option>
            <option value="high">Élevée</option>
            <option value="normal">Normale</option>
          </select>
          <select value={order} onChange={(e) => setOrder(e.target.value as "priority" | "time")} aria-label="Tri">
            <option value="priority">Tri par priorité</option>
            <option value="time">Tri chronologique</option>
          </select>
          <input type="text" className="filter-input" placeholder="Numéro fiscal" inputMode="numeric" maxLength={13}
            value={account} onChange={(e) => setAccount(e.target.value.replace(/\D/g, ""))} />
          <button type="button" className="btn-small" onClick={load}>Actualiser</button>
          <button type="button" className="btn-small" onClick={verify}>Vérifier l'intégrité</button>
        </div>
      </div>
      {error && <div className="alert error">{error}</div>}
      {integrity && <div className={`alert ${integrity.startsWith("ALT") ? "error" : "success"}`}>{integrity}</div>}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Horodatage (UTC)</th>
              <th>Priorité</th>
              <th>Compte</th>
              <th>Action</th>
              <th>Endpoint</th>
              <th>IP</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.seq} className={l.outcome === "failure" ? "row-failure" : ""}>
                <td className="mono small">{l.timestamp.replace("T", " ").replace("Z", "")}</td>
                <td><span className={`badge prio-${l.priority}`}>{PRIORITY_LABELS[l.priority]}</span></td>
                <td className="mono small">{l.account}</td>
                <td>{l.action}</td>
                <td className="mono small">{l.endpoint}</td>
                <td className="mono small">{l.ip}</td>
                <td className="mono small">{l.source}</td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={7} className="empty-state">Aucun événement.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
