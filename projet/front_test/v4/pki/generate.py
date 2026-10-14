"""
PKI de test (cahier des charges §2.3 — « mise en place d'une PKI pour
signer les certificats X.509 »).

Lancé par le service `pki` de docker-compose AVANT tous les autres :
- crée une autorité de certification racine (AC « Authentism Root CA »,
  ECDSA P-256, 5 ans) si elle n'existe pas ;
- délivre un certificat serveur à chaque composant (Nginx, webapp,
  auth-system, log-collector, LDAP, serveur mail), valable
  LEAF_DAYS jours ;
- RENOUVELLE automatiquement tout certificat qui expire dans moins de
  RENEW_BEFORE_DAYS jours, ou dont les noms (SAN) ont changé.

Chaque clé privée n'est lisible que par l'utilisateur (uid) du conteneur
qui l'utilise. Le certificat public de l'AC est copié dans /pki/ca.crt,
à importer dans le navigateur pour éviter l'avertissement HTTPS.
"""
import datetime as dt
import ipaddress
import os
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

OUT = os.environ.get("PKI_DIR", "/pki")
LEAF_DAYS = int(os.environ.get("PKI_LEAF_DAYS", "90"))
RENEW_BEFORE_DAYS = int(os.environ.get("PKI_RENEW_BEFORE_DAYS", "30"))
PUBLIC_HOSTNAMES = [h.strip() for h in os.environ.get("PUBLIC_HOSTNAMES", "localhost").split(",") if h.strip()]

# nom → (uid propriétaire de la clé, noms DNS / IP du certificat)
SERVICES = {
    "edge": (101, PUBLIC_HOSTNAMES + ["127.0.0.1", "::1"]),
    "webapp": (10001, ["webapp", "localhost", "127.0.0.1"]),
    "auth-system": (10002, ["auth-system", "localhost", "127.0.0.1"]),
    "log-collector": (10003, ["log-collector", "localhost", "127.0.0.1"]),
    "ldap": (0, ["ldap", "localhost"]),
    "mail": (0, ["mailpit", "localhost"]),
}

NOW = dt.datetime.now(dt.timezone.utc)


def _write(path: str, data: bytes, mode: int, uid: int) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.chmod(tmp, mode)
    if hasattr(os, "chown"):
        os.chown(tmp, uid, uid)
    os.replace(tmp, path)


def _pem_key(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def _load_or_create_ca():
    ca_dir = os.path.join(OUT, "ca")
    os.makedirs(ca_dir, exist_ok=True)
    os.chmod(ca_dir, 0o700)
    key_path, crt_path = os.path.join(ca_dir, "ca.key"), os.path.join(ca_dir, "ca.crt")
    if os.path.exists(key_path) and os.path.exists(crt_path):
        cert = x509.load_pem_x509_certificate(open(crt_path, "rb").read())
        if cert.not_valid_after_utc - NOW > dt.timedelta(days=RENEW_BEFORE_DAYS):
            key = serialization.load_pem_private_key(open(key_path, "rb").read(), password=None)
            return key, cert, False

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "FR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Authentism"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Authentism Root CA (test DGFiP)"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - dt.timedelta(minutes=5))
        .not_valid_after(NOW + dt.timedelta(days=5 * 365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                     content_commitment=False, key_encipherment=False, data_encipherment=False,
                                     key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    _write(key_path, _pem_key(key), 0o600, 0)
    _write(crt_path, cert.public_bytes(serialization.Encoding.PEM), 0o644, 0)
    print("[pki] Nouvelle autorité de certification racine créée.")
    return key, cert, True


def _san(names: list[str]):
    entries = []
    for n in names:
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            entries.append(x509.DNSName(n))
    return entries


def _needs_renewal(crt_path: str, names: list[str], ca_cert) -> str | None:
    if not os.path.exists(crt_path):
        return "absent"
    cert = x509.load_pem_x509_certificate(open(crt_path, "rb").read())
    if cert.issuer != ca_cert.subject:
        return "AC différente"
    if cert.not_valid_after_utc - NOW < dt.timedelta(days=RENEW_BEFORE_DAYS):
        return "expiration proche"
    current = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if set(map(str, current)) != set(map(str, _san(names))):
        return "noms modifiés"
    return None


def _issue(name: str, uid: int, names: list[str], ca_key, ca_cert) -> None:
    svc_dir = os.path.join(OUT, name)
    os.makedirs(svc_dir, exist_ok=True)
    crt_path, key_path = os.path.join(svc_dir, "tls.crt"), os.path.join(svc_dir, "tls.key")
    reason = _needs_renewal(crt_path, names, ca_cert)
    if reason:
        key = ec.generate_private_key(ec.SECP256R1())
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Authentism"),
                                     x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(NOW - dt.timedelta(minutes=5))
            .not_valid_after(NOW + dt.timedelta(days=LEAF_DAYS))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName(_san(names)), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
                           critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256())
        )
        _write(key_path, _pem_key(key), 0o600, uid)
        _write(crt_path, cert.public_bytes(serialization.Encoding.PEM), 0o644, uid)
        print(f"[pki] Certificat {name} délivré ({reason}), valable {LEAF_DAYS} jours : {', '.join(names)}")
    else:
        print(f"[pki] Certificat {name} valide, pas de renouvellement.")
    _write(os.path.join(svc_dir, "ca.crt"), ca_cert.public_bytes(serialization.Encoding.PEM), 0o644, uid)
    if hasattr(os, "chown"):
        os.chown(svc_dir, uid, uid)
    os.chmod(svc_dir, 0o700)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    os.chmod(OUT, 0o755)
    ca_key, ca_cert, _ = _load_or_create_ca()
    _write(os.path.join(OUT, "ca.crt"), ca_cert.public_bytes(serialization.Encoding.PEM), 0o644, 0)
    for name, (uid, names) in SERVICES.items():
        _issue(name, uid, names, ca_key, ca_cert)
    print("[pki] Terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
