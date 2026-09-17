from flask import Flask, jsonify

from admin_routes import bp as admin_bp
from auth_routes import bp as auth_bp
from config import Config
from extensions import cors, db, limiter
from seed import seed_demo_accounts
from services_routes import bp as services_bp


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    app.register_blueprint(auth_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def set_security_headers(response):
        # Défense en profondeur côté API — le CSP fin et le HSTS
        # définitif se règlent en général au niveau du reverse proxy.
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Ressource introuvable."}), 404

    @app.errorhandler(429)
    def rate_limited(_e):
        return jsonify({"error": "Trop de tentatives. Réessayez dans quelques instants."}), 429

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        db.create_all()
        seed_demo_accounts()

    return app


app = create_app()

if __name__ == "__main__":
    # En production : serveur WSGI (gunicorn/uwsgi) derrière un reverse
    # proxy TLS, jamais le serveur de développement Flask.
    app.run(debug=True, port=5000)
