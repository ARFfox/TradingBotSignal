"""Comptes et sessions du tableau de bord.

Les mots de passe ne sont JAMAIS stockés en clair ni transmis à qui que ce
soit : seul un condensé scrypt (avec sel aléatoire par compte) est écrit sur
disque. La création de compte passe par une saisie masquée dans le terminal.

Usage :
    python3 -m gold_agent.auth ajouter arf
    python3 -m gold_agent.auth lister
    python3 -m gold_agent.auth motdepasse arf
    python3 -m gold_agent.auth supprimer arf
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time
from pathlib import Path

FICHIER = Path.home() / ".gold_agent_comptes.json"

# Paramètres scrypt — coût volontairement élevé : un condensé volé doit rester
# coûteux à attaquer hors ligne.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
# 128 * N * r octets sont necessaires ; OpenSSL plafonne a ~32 Mo par defaut,
# d'ou un maxmem explicite avec de la marge.
SCRYPT_MAXMEM = 64 * 1024 * 1024
DUREE_SESSION = 12 * 3600          # secondes
LONGUEUR_MIN = 8

_SESSIONS: dict[str, dict] = {}
_VERROU = threading.Lock()
# Fenêtre anti-force-brute, par identifiant
_ECHECS: dict[str, list] = {}
MAX_ECHECS, FENETRE_ECHECS = 5, 300


def _charger() -> dict:
    if not FICHIER.exists():
        return {}
    try:
        return json.loads(FICHIER.read_text())
    except Exception:
        return {}


def _ecrire(d: dict) -> None:
    FICHIER.write_text(json.dumps(d, indent=2))
    FICHIER.chmod(0o600)          # lisible par le propriétaire uniquement


def _condenser(motdepasse: str, sel: bytes) -> str:
    return hashlib.scrypt(motdepasse.encode("utf-8"), salt=sel,
                          n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                          maxmem=SCRYPT_MAXMEM, dklen=64).hex()


def creer(nom: str, motdepasse: str) -> None:
    if len(motdepasse) < LONGUEUR_MIN:
        raise ValueError(f"mot de passe trop court ({LONGUEUR_MIN} caracteres minimum)")
    comptes = _charger()
    sel = secrets.token_bytes(16)
    comptes[nom] = {"sel": sel.hex(), "condense": _condenser(motdepasse, sel),
                    "cree_le": int(time.time())}
    _ecrire(comptes)


def verifier(nom: str, motdepasse: str) -> bool:
    """Vérifie un couple identifiant/mot de passe, avec limitation d'essais."""
    maintenant = time.time()
    with _VERROU:
        essais = [t for t in _ECHECS.get(nom, []) if maintenant - t < FENETRE_ECHECS]
        _ECHECS[nom] = essais
        if len(essais) >= MAX_ECHECS:
            return False

    c = _charger().get(nom)
    if not c:
        # Condensé factice : le temps de réponse ne doit pas révéler
        # si l'identifiant existe.
        _condenser(motdepasse, b"0" * 16)
        ok = False
    else:
        attendu = _condenser(motdepasse, bytes.fromhex(c["sel"]))
        ok = hmac.compare_digest(attendu, c["condense"])

    if not ok:
        with _VERROU:
            _ECHECS.setdefault(nom, []).append(maintenant)
    else:
        with _VERROU:
            _ECHECS.pop(nom, None)
    return ok


def ouvrir_session(nom: str) -> str:
    jeton = secrets.token_urlsafe(32)
    with _VERROU:
        _SESSIONS[jeton] = {"nom": nom, "expire": time.time() + DUREE_SESSION}
    return jeton


def session_valide(jeton: str | None) -> str | None:
    """Renvoie le nom du compte si la session est valable, sinon None."""
    if not jeton:
        return None
    with _VERROU:
        s = _SESSIONS.get(jeton)
        if not s:
            return None
        if s["expire"] < time.time():
            _SESSIONS.pop(jeton, None)
            return None
        return s["nom"]


def fermer_session(jeton: str | None) -> None:
    if jeton:
        with _VERROU:
            _SESSIONS.pop(jeton, None)


def comptes_existent() -> bool:
    return bool(_charger())


def lister() -> list[str]:
    return sorted(_charger())


def supprimer(nom: str) -> bool:
    comptes = _charger()
    if nom not in comptes:
        return False
    comptes.pop(nom)
    _ecrire(comptes)
    with _VERROU:
        for j, s in list(_SESSIONS.items()):
            if s["nom"] == nom:
                _SESSIONS.pop(j, None)
    return True


def _saisir_motdepasse() -> str:
    """Saisie masquée, jamais affichée ni journalisée."""
    while True:
        a = getpass.getpass("Mot de passe (masque) : ")
        if len(a) < LONGUEUR_MIN:
            print(f"  Trop court — {LONGUEUR_MIN} caracteres minimum.")
            continue
        b = getpass.getpass("Confirme               : ")
        if a != b:
            print("  Les deux saisies different.")
            continue
        return a


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    cmd = args[0]

    if cmd == "lister":
        noms = lister()
        print(f"{len(noms)} compte(s) : {', '.join(noms) if noms else 'aucun'}")
        print(f"fichier : {FICHIER}")
        return 0

    if cmd in ("ajouter", "motdepasse"):
        if len(args) < 2:
            print(f"usage : python3 -m gold_agent.auth {cmd} <identifiant>")
            return 1
        nom = args[1]
        existe = nom in _charger()
        if cmd == "ajouter" and existe:
            print(f"Le compte '{nom}' existe deja. Utilise 'motdepasse' pour le changer.")
            return 1
        if cmd == "motdepasse" and not existe:
            print(f"Le compte '{nom}' n'existe pas.")
            return 1
        try:
            creer(nom, _saisir_motdepasse())
        except ValueError as e:
            print(f"  {e}")
            return 1
        print(f"Compte '{nom}' {'cree' if cmd == 'ajouter' else 'mis a jour'}.")
        print(f"  Condense scrypt enregistre dans {FICHIER} (permissions 600).")
        print("  Le mot de passe lui-meme n'est stocke nulle part.")
        return 0

    if cmd == "supprimer":
        if len(args) < 2:
            print("usage : python3 -m gold_agent.auth supprimer <identifiant>")
            return 1
        print(f"Compte '{args[1]}' " + ("supprime." if supprimer(args[1]) else "introuvable."))
        return 0

    print(f"commande inconnue : {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
