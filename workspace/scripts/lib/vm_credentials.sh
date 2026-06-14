#!/usr/bin/env bash
# Password and SSL certificate generation for the workspace VM.
# Sourced by launch-mac.sh.

set -euo pipefail

# These globals are set by the calling script:
#   VMS_DIR, CONTAINER_NAME, log_ok, log_info, log_warn, log_error

PASSWORD_FILE="${VMS_DIR}/${CONTAINER_NAME}/password"
CERT_DIR="${VMS_DIR}/${CONTAINER_NAME}/certs"

generate_password() {
    local vm_dir="${VMS_DIR}/${CONTAINER_NAME}"
    mkdir -p "$vm_dir"

    if [[ -f "$PASSWORD_FILE" ]]; then
        log_ok "Password already exists at $PASSWORD_FILE"
        return 0
    fi

    log_info "Generating random password..."
    local password
    password=$(openssl rand -base64 18 | tr -d '/+=' | head -c 24)
    printf '%s' "$password" > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
    log_ok "Password generated and saved to $PASSWORD_FILE"
}

get_password() {
    if [[ -f "$PASSWORD_FILE" ]]; then
        cat "$PASSWORD_FILE"
    else
        echo ""
    fi
}

generate_ssl_certs() {
    local vm_dir="${VMS_DIR}/${CONTAINER_NAME}"
    local certs_dir="${vm_dir}/certs"
    mkdir -p "$certs_dir"

    if [[ -f "${certs_dir}/ca.crt" && -f "${certs_dir}/server.crt" && -f "${certs_dir}/server.key" ]]; then
        log_ok "SSL certificates already exist"
        return 0
    fi

    log_info "Generating self-signed SSL certificates..."

    openssl genrsa -out "${certs_dir}/ca.key" 4096
    openssl req -new -x509 -days 3650 -key "${certs_dir}/ca.key" \
        -out "${certs_dir}/ca.crt" \
        -subj "/C=US/ST=State/L=City/O=Workspace/OU=VM/CN=Workspace CA"

    openssl genrsa -out "${certs_dir}/server.key" 2048
    openssl req -new -key "${certs_dir}/server.key" \
        -out "${certs_dir}/server.csr" \
        -subj "/C=US/ST=State/L=City/O=Workspace/OU=VM/CN=localhost"

    openssl x509 -req -days 365 \
        -in "${certs_dir}/server.csr" \
        -CA "${certs_dir}/ca.crt" \
        -CAkey "${certs_dir}/ca.key" \
        -CAcreateserial \
        -out "${certs_dir}/server.crt"

    rm -f "${certs_dir}/server.csr" "${certs_dir}/ca.srl"

    log_ok "SSL certificates generated in $certs_dir"
}
