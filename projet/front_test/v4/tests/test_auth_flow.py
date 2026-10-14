import json

from conftest import ADMIN, AGENT, EXTERNAL, HDR, LOG_FILE, admin_login, login


# --- Authentification (cahier des charges §2.1) ------------------------
def test_login_mfa_and_session_cookie(web):
    user = login(web, AGENT)
    assert user["role"] == "agent" and user["redirect"] == "/dashboard.php"
    cookie = web.get_cookie("dgfip_session")
    assert cookie is not None and cookie.http_only and cookie.same_site == "Strict"
    assert web.get("/session").get_json()["fiscal_id"] == AGENT[0]


def test_wrong_password_is_generic_and_locks_after_5(web):
    for _ in range(5):
        res = web.post("/login.php", json={"fiscal_id": AGENT[0], "password": "Wrong!Password1"}, headers=HDR)
        assert res.status_code == 401
        assert res.get_json()["error"] == "Identifiant ou mot de passe incorrect."
    res = web.post("/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]}, headers=HDR)
    assert res.status_code == 423


def test_unknown_account_same_error(web):
    res = web.post("/login.php", json={"fiscal_id": "9999999999999", "password": "Whatever!12345"}, headers=HDR)
    assert res.status_code == 401
    assert res.get_json()["error"] == "Identifiant ou mot de passe incorrect."


def test_injection_payloads_rejected(web):
    for payload in ("*", "*)(uid=*", "1032005849213)(|(uid=*", "<script>alert(1)</script>",
                    "1; rm -rf /", "' OR 1=1 --"):
        res = web.post("/login.php", json={"fiscal_id": payload, "password": "x"}, headers=HDR)
        assert res.status_code == 401


def test_mfa_three_failures_terminate(web):
    res = web.post("/login.php", json={"fiscal_id": EXTERNAL[0], "password": EXTERNAL[1]}, headers=HDR)
    token = res.get_json()["challenge_token"]
    for expected in (2, 1):
        res = web.post("/login.php/verify", json={"challenge_token": token, "code": "000000"}, headers=HDR)
        assert res.get_json()["attempts_remaining"] == expected
    res = web.post("/login.php/verify", json={"challenge_token": token, "code": "000000"}, headers=HDR)
    assert res.status_code == 401 and res.get_json()["restart"] is True
    res = web.post("/login.php/verify", json={"challenge_token": token, "code": "000000"}, headers=HDR)
    assert res.status_code == 400


def test_mfa_code_single_use(web):
    res = web.post("/login.php", json={"fiscal_id": EXTERNAL[0], "password": EXTERNAL[1]}, headers=HDR)
    data = res.get_json()
    body = {"challenge_token": data["challenge_token"], "code": data["debug_code"]}
    assert web.post("/login.php/verify", json=body, headers=HDR).status_code == 200
    assert web.post("/login.php/verify", json=body, headers=HDR).status_code == 400


def test_logout_revokes_session(web):
    login(web, AGENT)
    assert web.post("/logout", headers=HDR).status_code == 200
    assert web.get("/dashboard.php").status_code == 401


# --- Whitelist / CSRF (§2.5) -------------------------------------------
def test_unknown_endpoint_denied(web):
    assert web.get("/etc/passwd").status_code == 404
    assert web.get("/dashboard.php").status_code == 401


def test_csrf_header_required(web):
    res = web.post("/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]})
    assert res.status_code == 403


# --- RBAC (Modèle RBAC à implémenter.pdf) -------------------------------
def test_dashboard_and_rbac_per_role(web):
    login(web, EXTERNAL)
    links = {link["slug"]: link["allowed"] for link in web.get("/dashboard.php").get_json()["links"]}
    assert links == {"page1": True, "outils-agents": False, "admin": False}
    assert web.get("/page1.php").status_code == 200
    assert web.get("/outils-agents.php").status_code == 403
    assert web.get("/inexistante.php").status_code == 404


def test_non_admin_cannot_get_admin_token(web):
    login(web, AGENT)
    res = web.post("/admin.php/token", json={"password": AGENT[1]}, headers=HDR)
    assert res.status_code == 403
    assert web.get("/admin.php/users").status_code == 403


def test_admin_token_requires_password_and_is_scoped(web):
    login(web, ADMIN)
    assert web.post("/admin.php/token", json={"password": "Mauvais!Mdp123"}, headers=HDR).status_code == 401
    assert web.get("/admin.php").status_code == 403
    assert web.post("/admin.php/token", json={"password": ADMIN[1]}, headers=HDR).status_code == 200
    assert web.get("/admin.php").status_code == 200
    # Le jeton admin seul (sans la session dont il est issu) ne vaut rien.
    web.post("/logout", headers=HDR)
    assert web.get("/admin.php").status_code == 401


def test_admin_account_lifecycle(web):
    admin_login(web)
    new = {"fiscal_id": "4000000000001", "name": "Jean Test", "email": "jean.test@example.org",
           "role": "external", "password": "Nouveau!Compte26"}
    assert web.post("/admin.php/users", json={**new, "password": "faible"}, headers=HDR).status_code == 400
    assert web.post("/admin.php/users", json=new, headers=HDR).status_code == 201
    assert web.post("/admin.php/users", json=new, headers=HDR).status_code == 409

    other = web.application.test_client()
    login(other, (new["fiscal_id"], new["password"]))
    assert other.get("/outils-agents.php").status_code == 403

    # Changement de rôle → sessions de l'utilisateur révoquées
    res = web.patch(f"/admin.php/users/{new['fiscal_id']}", json={"role": "agent"}, headers=HDR)
    assert res.status_code == 200
    assert other.get("/dashboard.php").status_code == 401
    login(other, (new["fiscal_id"], new["password"]))
    assert other.get("/outils-agents.php").status_code == 200

    # Mot de passe modifié par l'admin
    assert web.post(f"/admin.php/users/{new['fiscal_id']}/password", json={"new_password": "Autre!Secret2026"},
                    headers=HDR).status_code == 200
    assert other.get("/dashboard.php").status_code == 401
    login(other, (new["fiscal_id"], "Autre!Secret2026"))

    users = {u["fiscal_id"]: u for u in web.get("/admin.php/users").get_json()}
    assert users[new["fiscal_id"]]["role"] == "agent"

    assert web.delete(f"/admin.php/users/{new['fiscal_id']}", headers=HDR).status_code == 200
    res = other.post("/login.php", json={"fiscal_id": new["fiscal_id"], "password": "Autre!Secret2026"}, headers=HDR)
    assert res.status_code == 401


def test_admin_cannot_delete_or_demote_self(web):
    admin_login(web)
    assert web.delete(f"/admin.php/users/{ADMIN[0]}", headers=HDR).status_code == 400
    assert web.patch(f"/admin.php/users/{ADMIN[0]}", json={"role": "agent"}, headers=HDR).status_code == 400


def test_admin_edits_dashboard_pages(web):
    admin_login(web)
    page = {"slug": "simulateur", "label": "Simulateur d'impôt", "description": "Estimez votre impôt",
            "content": "Simulateur", "roles": ["agent", "admin"], "visible": True}
    assert web.post("/admin.php/pages", json={**page, "label": "<script>"}, headers=HDR).status_code == 400
    assert web.post("/admin.php/pages", json={**page, "slug": "admin"}, headers=HDR).status_code == 400
    assert web.post("/admin.php/pages", json=page, headers=HDR).status_code == 201

    ext = web.application.test_client()
    login(ext, EXTERNAL)
    assert ext.get("/simulateur.php").status_code == 403
    assert web.put("/admin.php/pages/simulateur", json={**page, "roles": ["external", "agent", "admin"]},
                   headers=HDR).status_code == 200
    assert ext.get("/simulateur.php").status_code == 200
    assert web.delete("/admin.php/pages/simulateur", headers=HDR).status_code == 200
    assert ext.get("/simulateur.php").status_code == 404


# --- Réinitialisation de son mot de passe --------------------------------
def test_password_reset_flow(web):
    res = web.post("/password/forgot", json={"fiscal_id": EXTERNAL[0]}, headers=HDR)
    data = res.get_json()
    assert "debug_code" in data
    body = {"challenge_token": data["challenge_token"], "code": data["debug_code"]}
    assert web.post("/password/reset", json={**body, "new_password": "court"}, headers=HDR).status_code == 400
    assert web.post("/password/reset", json={**body, "new_password": "Nouveau!Usager26"}, headers=HDR).status_code == 200
    login(web, (EXTERNAL[0], "Nouveau!Usager26"))
    # remise en état pour les autres tests
    data = web.post("/password/forgot", json={"fiscal_id": EXTERNAL[0]}, headers=HDR).get_json()
    web.post("/password/reset", json={"challenge_token": data["challenge_token"], "code": data["debug_code"],
                                      "new_password": EXTERNAL[1]}, headers=HDR)


def test_password_forgot_unknown_account_does_not_leak(web):
    res = web.post("/password/forgot", json={"fiscal_id": "9999999999998"}, headers=HDR)
    assert res.status_code == 200 and "debug_code" not in res.get_json()


# --- Traçabilité (§3.2) --------------------------------------------------
def test_logs_contain_required_fields_and_chain_detects_tampering(web):
    admin_login(web)
    logs = web.get("/admin.php/logs").get_json()
    assert logs and all({"timestamp", "account", "action", "endpoint", "ip"} <= e.keys() for e in logs)
    assert logs[0]["priority"] == "critical" or logs[0]["priority"] == "high"
    assert any(e["ip"] == "203.0.113.7" for e in logs)
    assert web.get("/admin.php/logs/verify").get_json()["valid"] is True

    with open(LOG_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    original = list(lines)
    event = json.loads(lines[0])
    event["account"] = "falsifie"
    lines[0] = json.dumps(event, ensure_ascii=False) + "\n"
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)
    assert web.get("/admin.php/logs/verify").get_json()["valid"] is False
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(original)


def test_ip_throttle_counts_only_failures(web):
    import auth_service
    for _ in range(auth_service.IP_MAX_ATTEMPTS + 5):
        login(web, AGENT)  # les succès ne comptent pas
    hdr = {**HDR, "X-Real-IP": "198.51.100.9"}
    for i in range(auth_service.IP_MAX_ATTEMPTS):
        web.post("/login.php", json={"fiscal_id": f"{i:013d}", "password": "Faux!Essai2026"}, headers=hdr)
    res = web.post("/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]}, headers=hdr)
    assert res.status_code == 429


def test_same_origin_accepted_for_any_host(web):
    for host, origin in (("localhost", "https://localhost"), ("127.0.0.1", "https://127.0.0.1"),
                         ("pc-victor:8443", "https://pc-victor:8443")):
        res = web.post("/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]},
                       headers={**HDR, "Origin": origin, "Host": host, "X-Forwarded-Proto": "https"})
        assert res.status_code == 200, (origin, res.get_json())


def test_cross_site_origin_rejected(web):
    res = web.post("/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]},
                   headers={**HDR, "Origin": "https://evil.example", "Host": "localhost", "X-Forwarded-Proto": "https"})
    assert res.status_code == 403
