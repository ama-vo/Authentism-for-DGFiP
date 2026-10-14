// Gestion des erreurs commune aux onglets d'administration :
// si le jeton d'administration a expiré (15 min), on revient au formulaire de mot de passe.
import { useState } from "react";
import { ApiError, errorMessage } from "../../api";
import { useAuth } from "../../AuthContext";

export function useAdminError() {
  const { refresh } = useAuth();
  const [error, setError] = useState("");

  function handleError(err: unknown) {
    if (err instanceof ApiError && err.code === "ADMIN_SESSION_REQUIRED") {
      refresh();
      return;
    }
    setError(errorMessage(err));
  }

  return { error, setError, handleError };
}
