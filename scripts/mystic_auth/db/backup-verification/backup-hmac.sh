#!/usr/bin/env bash
# Detached HMAC-SHA256 tamper-evidence for backup ciphertext.
#
# Backups are encrypted with AES-256-CBC via `openssl enc` (see
# database-backup.sh), which has no authenticated-encryption mode of its own:
# `openssl enc -aes-256-gcm` fails outright with "AEAD ciphers not
# supported" (this is a limitation of the `enc` subcommand itself, not a
# missing OpenSSL build flag). CBC alone gives confidentiality but no
# cryptographic tamper-evidence - this adds the missing half via a classic
# encrypt-then-MAC construction: a detached HMAC-SHA256 tag written
# alongside the ciphertext as "<file>.hmac".
#
# The MAC key is NOT the AES passphrase itself - it's HMAC-SHA256 of a fixed
# label keyed by that passphrase, a one-way derivation that keeps the MAC
# key and the (PBKDF2-stretched) encryption key independent, so a leaked
# .hmac tag doesn't hand an attacker anything useful against the ciphertext.
#
# Usage:
#   backup-hmac.sh tag    <file> <passphrase>   writes <file>.hmac
#   backup-hmac.sh verify <file> <passphrase>   exit 0 if <file>.hmac matches
#                                                the file's current contents,
#                                                exit 1 if it exists and
#                                                doesn't match, exit 2 if no
#                                                .hmac file exists at all
#
# Used both on the host (database-backup.sh, database-restore.sh - this script and
# OpenSSL are the only dependencies, no sourcing needed) and inside the
# db_backup container's own long-running loop (copied in as
# /usr/local/bin/backup-hmac by db-backup.Dockerfile), so the exact same
# logic runs either way rather than two hand-kept copies.
set -euo pipefail

mac_key() {
  printf '%s' "mystic-auth-backup-mac-v1" | openssl dgst -sha256 -hmac "$1" | awk '{print $NF}'
}

tag_file() {
  local file="$1" passphrase="$2" key
  key="$(mac_key "$passphrase")"
  openssl dgst -sha256 -hmac "$key" "$file" | awk '{print $NF}' > "${file}.hmac"
}

verify_file() {
  local file="$1" passphrase="$2" key expected actual
  if [ ! -f "${file}.hmac" ]; then
    return 2
  fi
  key="$(mac_key "$passphrase")"
  expected="$(cat "${file}.hmac")"
  actual="$(openssl dgst -sha256 -hmac "$key" "$file" | awk '{print $NF}')"
  [ "$expected" = "$actual" ]
}

case "${1:-}" in
  tag)
    tag_file "${2:?file is required}" "${3:?passphrase is required}"
    ;;
  verify)
    verify_file "${2:?file is required}" "${3:?passphrase is required}"
    ;;
  *)
    echo "Usage: $0 tag|verify <file> <passphrase>" >&2
    exit 2
    ;;
esac
