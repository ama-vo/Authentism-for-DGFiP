from extensions import db
from models import User
from security import hash_password

DEMO_ACCOUNTS = [
    # ATTENTION : mots de passe de démonstration uniquement, à ne
    # jamais réutiliser tels quels. Ils respectent la politique du
    # cahier des charges (12+ caractères, maj/min/chiffre/spécial).
    {"fiscal_id": "1032005849213", "name": "Camille Dubreuil", "role": "agent", "password": "Agent!DGFiP2026"},
    {"fiscal_id": "2098741562034", "name": "Yanis Belkacem", "role": "external", "password": "Usager!Externe26"},
    {"fiscal_id": "3011008876521", "name": "Sophie Mercier", "role": "admin", "password": "Admin!SysDGFiP26"},
]


def seed_demo_accounts():
    if User.query.first():
        return
    for acc in DEMO_ACCOUNTS:
        db.session.add(User(
            fiscal_id=acc["fiscal_id"],
            name=acc["name"],
            email=f"{acc['fiscal_id']}@dgfip-demo.local",
            password_hash=hash_password(acc["password"]),
            role=acc["role"],
        ))
    db.session.commit()
