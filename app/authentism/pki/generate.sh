#!/bin/sh
# =============================================================
#  PKI Authentism : crée une autorité de certification (CA)
#  puis signe le certificat X.509 du site web (HTTPS).
#  Le script ne fait rien si les certificats existent déjà.
#  Renouvellement : supprimer le volume certs-web puis relancer
#  -> nouveau certificat signé par la même CA.
# =============================================================
set -e

if [ -f /out/web/server.crt ]; then
  echo "[pki] Certificats déjà présents, rien à faire."
  exit 0
fi

apk add --no-cache openssl > /dev/null
WORK=$(mktemp -d)
cd "$WORK"

echo "[pki] 1. Autorité de certification (CA)"
if [ -f /out/ca/ca.key ]; then
  cp /out/ca/ca.key /out/ca/ca.crt .   # on réutilise la CA existante
else
  openssl genrsa -out ca.key 4096
  openssl req -x509 -new -key ca.key -sha256 -days 3650 \
    -subj "/C=FR/O=Authentism/CN=Authentism Root CA" -out ca.crt
  cp ca.key ca.crt /out/ca/
  chmod 600 /out/ca/ca.key
fi

# Fonction : sign <nom> <CN> <SAN>
sign() {
  openssl genrsa -out "$1.key" 2048
  openssl req -new -key "$1.key" -subj "/C=FR/O=DGFiP/CN=$2" -out "$1.csr"
  printf "subjectAltName=%s\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$3" > "$1.ext"
  openssl x509 -req -in "$1.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days 397 -sha256 -extfile "$1.ext" -out "$1.crt"
}

echo "[pki] 2. Certificat du site web (localhost)"
sign server localhost "DNS:localhost,IP:127.0.0.1"

cp server.crt server.key ca.crt /out/web/
chmod 644 /out/web/*
# La clé privée de la CA reste dans son propre volume (pki-ca), monté uniquement ici.
echo "[pki] Terminé."
