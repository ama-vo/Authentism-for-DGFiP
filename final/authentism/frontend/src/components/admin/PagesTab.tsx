// Onglet "Pages du dashboard" : l'admin choisit les pages visibles et modifie leur texte
import { useEffect, useState } from "react";
import { api } from "../../api";
import { Page } from "../../types";
import { useAdminError } from "./useAdminError";

export default function PagesTab() {
  const { error, setError, handleError } = useAdminError();
  const [pages, setPages] = useState<Page[]>([]);
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api<{ pages: Page[] }>("/admin/pages")
      .then((data) => setPages(data.pages))
      .catch(handleError);
  }, []);

  // Modifie un champ d'une page dans l'état local (avant enregistrement)
  function edit(slug: string, changes: Partial<Page>) {
    setPages(pages.map((p) => (p.slug === slug ? { ...p, ...changes } : p)));
  }

  async function save(page: Page) {
    setError("");
    setSuccess("");
    try {
      const { title, description, content, visible } = page;
      await api(`/admin/pages/${page.slug}`, "PUT", { title, description, content, visible });
      setSuccess(`Page « ${page.title} » enregistrée`);
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <>
      {error && <p className="alert error">{error}</p>}
      {success && <p className="alert success">{success}</p>}

      {pages.map((page) => (
        <div key={page.slug} className={`card ${page.visible ? "" : "card-hidden"}`}>
          <label className="checkbox">
            <input type="checkbox" checked={page.visible} onChange={(e) => edit(page.slug, { visible: e.target.checked })} />
            Visible sur le dashboard
          </label>

          <label>Titre</label>
          <input maxLength={80} value={page.title} onChange={(e) => edit(page.slug, { title: e.target.value })} />

          <label>Description (menu)</label>
          <input maxLength={200} value={page.description} onChange={(e) => edit(page.slug, { description: e.target.value })} />

          <label>Contenu</label>
          <textarea rows={3} maxLength={2000} value={page.content} onChange={(e) => edit(page.slug, { content: e.target.value })} />

          <button className="btn" onClick={() => save(page)}>Enregistrer</button>
        </div>
      ))}
    </>
  );
}
