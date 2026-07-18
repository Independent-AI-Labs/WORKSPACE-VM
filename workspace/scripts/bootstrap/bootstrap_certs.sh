#!/usr/bin/env bash
set -euo pipefail
OP="bootstrap_certs"

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <uuid> <output-dir>"
    echo "  Generates CA + server cert + client cert for a VM."
    exit 2
fi

VM_UUID="$1"
CERT_DIR="$2"

if ! command -v openssl ; then
    echo "[${OP}] openssl is required but not available"
    exit 1
fi

mkdir -p "$CERT_DIR"

CA_KEY="${CERT_DIR}/ca.key"
CA_CRT="${CERT_DIR}/ca.crt"
SERVER_KEY="${CERT_DIR}/server.key"
SERVER_CSR="/tmp/ami-vm-server-${VM_UUID}.csr"
SERVER_CRT="${CERT_DIR}/server.crt"
CLIENT_KEY="${CERT_DIR}/client.key"
CLIENT_CSR="/tmp/ami-vm-client-${VM_UUID}.csr"
CLIENT_CRT="${CERT_DIR}/client.crt"
SERIAL="${CERT_DIR}/ca.srl"

CN="${VM_UUID}.vm.local"

if [[ -f "$CA_CRT" ]] && [[ -f "$SERVER_CRT" ]] && [[ -f "$CLIENT_CRT" ]]; then
    echo "[${OP}] certs already exist in ${CERT_DIR}, skipping"
    exit 0
fi

echo "[${OP}] Generating CA..."
openssl genrsa -out "$CA_KEY" 4096
openssl req -x509 -new -nodes -key "$CA_KEY" -sha512 -days 3650 \
    -out "$CA_CRT" -subj "/CN=${VM_UUID}-CA"

echo "[${OP}] Generating server cert (CN=${CN})..."
openssl genrsa -out "$SERVER_KEY" 4096
openssl req -new -key "$SERVER_KEY" -out "$SERVER_CSR" \
    -subj "/CN=${CN}"
openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
    -CAcreateserial -out "$SERVER_CRT" -days 3650 -sha512

echo "[${OP}] Generating client cert (CN=ami-admin)..."
openssl genrsa -out "$CLIENT_KEY" 4096
openssl req -new -key "$CLIENT_KEY" -out "$CLIENT_CSR" \
    -subj "/CN=ami-admin"
openssl x509 -req -in "$CLIENT_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
    -CAserial "$SERIAL" -out "$CLIENT_CRT" -days 3650 -sha512

chmod 600 "$CA_KEY" "$SERVER_KEY" "$CLIENT_KEY"
rm -f "$SERVER_CSR" "$CLIENT_CSR"
echo "[${OP}] certs generated → ${CERT_DIR}"
