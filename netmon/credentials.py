"""Senhas guardadas no Gerenciador de Credenciais do Windows (via keyring).

Uso pelo terminal (na pasta do projeto):
    python -m netmon.credentials painel        -> define/troca a senha do painel
    python -m netmon.credentials painel --remover
    python -m netmon.credentials ont           -> define/troca a senha SSH da ONT
"""
import getpass
import hashlib
import hmac
import os
import secrets
import sys

import keyring
from keyring.errors import KeyringError

ONT_SERVICE = "NetMon-ONT"
PANEL_SERVICE = "NetMon-Painel"
PANEL_ACCOUNT = "painel"


# --- Senha SSH da ONT ----------------------------------------------------
def get_ont_password(user):
    """Senha da ONT: Gerenciador de Credenciais primeiro, .env (ONT_PASS) como reserva."""
    if user:
        try:
            pwd = keyring.get_password(ONT_SERVICE, user)
            if pwd:
                return pwd, "keyring"
        except KeyringError:
            pass
    pwd = os.getenv("ONT_PASS", "")
    return pwd, ("env" if pwd else None)


def set_ont_password(user, password):
    keyring.set_password(ONT_SERVICE, user, password)


def migrate_ont_password_from_env(user):
    """Copia ONT_PASS do .env para o Gerenciador de Credenciais, se ainda não estiver lá."""
    env_pwd = os.getenv("ONT_PASS", "")
    if not user or not env_pwd:
        return False
    try:
        if keyring.get_password(ONT_SERVICE, user):
            return False
        keyring.set_password(ONT_SERVICE, user, env_pwd)
        return keyring.get_password(ONT_SERVICE, user) == env_pwd
    except KeyringError:
        return False


# --- Senha do painel (guardada só como hash) --------------------------------
def _hash(password, salt, iterations=200_000):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()


def panel_password_enabled():
    try:
        return bool(keyring.get_password(PANEL_SERVICE, PANEL_ACCOUNT))
    except KeyringError:
        return False


def set_panel_password(password):
    salt = secrets.token_hex(16)
    keyring.set_password(PANEL_SERVICE, PANEL_ACCOUNT, f"{salt}${_hash(password, salt)}")


def remove_panel_password():
    try:
        keyring.delete_password(PANEL_SERVICE, PANEL_ACCOUNT)
    except KeyringError:
        pass


def check_panel_password(password):
    try:
        stored = keyring.get_password(PANEL_SERVICE, PANEL_ACCOUNT)
    except KeyringError:
        return False
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    return hmac.compare_digest(_hash(password, salt), digest)


# --- Linha de comando ------------------------------------------------------
def _ask_new_password(label):
    while True:
        p1 = getpass.getpass(f"Nova senha {label}: ")
        if len(p1) < 6:
            print("Use pelo menos 6 caracteres.")
            continue
        if p1 != getpass.getpass("Repita a senha: "):
            print("As senhas não conferem, tente de novo.")
            continue
        return p1


def main(argv):
    if not argv or argv[0] not in ("painel", "ont"):
        print(__doc__)
        return 1
    if argv[0] == "painel":
        if "--remover" in argv:
            remove_panel_password()
            print("Senha do painel removida: o acesso pela rede ficou livre.")
            return 0
        set_panel_password(_ask_new_password("do painel"))
        print("Senha do painel salva no Gerenciador de Credenciais do Windows.")
        print("Acessos de outros aparelhos (ex.: celular) vão pedir essa senha.")
        return 0
    from .config import ROOT  # noqa: F401  (carrega o .env)
    user = os.getenv("ONT_USER") or input("Usuário SSH da ONT: ").strip()
    set_ont_password(user, _ask_new_password(f"SSH da ONT (usuário {user})"))
    print("Senha da ONT salva no Gerenciador de Credenciais do Windows.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
