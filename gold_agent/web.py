"""Tableau de bord local : python3 -m gold_agent.web

Serveur HTTP minimal (bibliothèque standard, aucune dépendance). Les données
sont recalculées à chaque chargement — un tableau de bord de trading qui
affiche des prix périmés est pire qu'inutile.
"""
from __future__ import annotations

import argparse
import http.server
import json
import shutil
import socket
import socketserver
import subprocess
import threading
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from . import auth, config as _cfg, datasource as ds, indicators as _ind, notify, patterns as _pat, structure as _st, tableau

PORT = 8787

from .pages import CSS, PAGE_CONNEXION, PAGE_CREATION  # noqa: F401
from .blocs import (_boule, _carte, _fragment_graphe,  # noqa: F401
                    _grand_graphique, _grille, _panneau_agents)
from .onglets import (_bloc_constellation, _bloc_marches,  # noqa: F401
                      _blocs_onglets)
from .blocs import WIDGET_TV  # noqa: F401
from .cerveau_js import CERVEAU_JS  # noqa: F401

from .rendu import rendre, surveiller  # noqa: F401

class Handler(http.server.BaseHTTPRequestHandler):

    def _jeton(self) -> str | None:
        brut = self.headers.get("Cookie", "")
        for morceau in brut.split(";"):
            k, _, v = morceau.strip().partition("=")
            if k == "session":
                return v
        return None

    def _repondre(self, corps: bytes, ctype: str, entetes: list | None = None,
                  code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (entetes or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corps)

    def do_POST(self):
        if self.path == "/reparer":
            if auth.comptes_existent() and not auth.session_valide(self._jeton()):
                self._repondre(b'{"erreur":"non authentifie"}',
                               "application/json; charset=utf-8", code=401)
                return
            import urllib.parse as _up
            taille = min(int(self.headers.get("Content-Length", 0) or 0), 1024)
            champs = _up.parse_qs(self.rfile.read(taille).decode("utf-8", "replace"))
            action = (champs.get("action") or [""])[0]
            try:
                message = _cfg.appliquer(action)
                corps = json.dumps({"ok": True, "message": message}, ensure_ascii=False)
            except Exception as e:
                corps = json.dumps({"ok": False, "message": str(e)[:150]}, ensure_ascii=False)
            self._repondre(corps.encode(), "application/json; charset=utf-8")
            return
        if self.path not in ("/connexion", "/creer"):
            self._repondre(b"introuvable", "text/plain", code=404)
            return
        import urllib.parse
        taille = min(int(self.headers.get("Content-Length", 0) or 0), 4096)
        champs = urllib.parse.parse_qs(self.rfile.read(taille).decode("utf-8", "replace"))
        nom = (champs.get("nom") or [""])[0].strip().lower()
        mdp = (champs.get("motdepasse") or [""])[0]

        if self.path == "/creer":
            # Uniquement tant qu'AUCUN compte n'existe : sinon n'importe qui
            # sur la machine pourrait s'ajouter un acces.
            if auth.comptes_existent():
                self._repondre(b"interdit", "text/plain", code=403)
                return
            mdp2 = (champs.get("motdepasse2") or [""])[0]
            erreur = None
            if "@" not in nom or "." not in nom.split("@")[-1]:
                erreur = "Adresse e-mail invalide."
            elif len(mdp) < 10:
                erreur = "Mot de passe trop court : 10 caractères minimum."
            elif mdp != mdp2:
                erreur = "Les deux mots de passe ne correspondent pas."
            if erreur:
                page = PAGE_CREATION.replace("{erreur}", f'<div class="err">{erreur}</div>')
                self._repondre(page.encode(), "text/html; charset=utf-8", code=400)
                return
            auth.creer(nom, mdp)
            jeton = auth.ouvrir_session(nom)
            self._repondre(b"", "text/plain", code=303, entetes=[
                ("Location", "/"),
                ("Set-Cookie", f"session={jeton}; HttpOnly; SameSite=Strict; Path=/"),
            ])
            return

        attente = auth.attente_requise(nom)
        if attente:
            page = PAGE_CONNEXION.replace("{erreur}",
                f'<div class="err">Trop d&#39;échecs — réessaie dans {attente} s.</div>')
            self._repondre(page.encode(), "text/html; charset=utf-8", code=429)
            return
        if nom and auth.verifier(nom, mdp):
            jeton = auth.ouvrir_session(nom)
            # HttpOnly : inaccessible au JavaScript de la page. SameSite=Strict :
            # le cookie ne part jamais depuis un autre site.
            self._repondre(b"", "text/plain", code=303, entetes=[
                ("Location", "/"),
                ("Set-Cookie", f"session={jeton}; HttpOnly; SameSite=Strict; Path=/"),
            ])
        else:
            page = PAGE_CONNEXION.replace("{erreur}",
                '<div class="err">Adresse ou mot de passe incorrect.</div>')
            self._repondre(page.encode(), "text/html; charset=utf-8", code=401)

    def do_GET(self):
        # Deconnexion
        if self.path == "/deconnexion":
            auth.fermer_session(self._jeton())
            self._repondre(b"", "text/plain", code=303, entetes=[
                ("Location", "/"),
                ("Set-Cookie", "session=; Max-Age=0; Path=/"),
            ])
            return

        # Tant qu'aucun compte n'existe, pas d'ecran de connexion : exiger un
        # mot de passe inexistant reviendrait a verrouiller l'utilisateur dehors.
        if not auth.comptes_existent() and self.path == "/":
            self._repondre(PAGE_CREATION.replace("{erreur}", "").encode(),
                           "text/html; charset=utf-8")
            return

        if auth.comptes_existent() and not auth.session_valide(self._jeton()):
            if self.path.startswith(("/json", "/api/")):
                self._repondre(b'{"erreur":"non authentifie"}',
                               "application/json; charset=utf-8", code=401)
            else:
                self._repondre(PAGE_CONNEXION.replace("{erreur}", "").encode(),
                               "text/html; charset=utf-8", code=401)
            return

        if self.path.startswith("/api/graphe"):
            g = (getattr(tableau, "DERNIER_PAQUET", None) or {}).get("graphe") \
                or {"noeuds": [], "liens": []}
            corps = json.dumps(g, ensure_ascii=False).encode()
            self._repondre(corps, "application/json; charset=utf-8")
            return

        if self.path.startswith("/cerveau.js"):
            corps = CERVEAU_JS.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
            return
        if self.path.startswith("/json"):
            # On renvoie les donnees ET le HTML des cartes dans la meme reponse :
            # une seule requete, et le rendu reste ecrit a un seul endroit
            # (pas de duplication de la mise en page en JavaScript).
            try:
                d = tableau.collecter()
                charge = {
                    "prix": d.get("prix"),
                    "genere_le": d["genere_le"],
                    "nb_setups": d["nb_setups"],
                    "suspension": d.get("suspension"),
                    "signaux": [
                        {"tf": r["nom"],
                         "sens": (r.get("setup") or {}).get("setup"),
                         "entree": (r.get("setup") or {}).get("entree"),
                         "stop": (r.get("setup") or {}).get("stop"),
                         "objectif": (r.get("setup") or {}).get("objectif"),
                         "rr": (r.get("setup") or {}).get("rr"),
                         "declenche": (r.get("setup") or {}).get("declenche"),
                         "fiabilite": (r.get("fiabilite") or {}).get("niveau")}
                        for r in d["timeframes"]
                        if (r.get("setup") or {}).get("setup")
                        and not (r.get("setup") or {}).get("suspendu")
                    ],
                    "html": _grille(d),
                    "news": d.get("news"),
                    "boule": _boule(d.get("consensus")),
                    "sante": d.get("sante"),
                    "sys_agents": _panneau_agents(d),
                    "quota": ds.COMPTEUR["twelvedata"],
                    "rotation": ds.etat_rotation(),
                    "quote": d.get("quote"),
                    "usage": d.get("usage"),
                }
                corps = json.dumps(charge, ensure_ascii=False).encode()
            except Exception as e:
                corps = json.dumps({"erreur": str(e)[:200]}).encode()
            ctype = "application/json; charset=utf-8"
        else:
            try:
                d = tableau.collecter()
                corps = rendre(d).encode()
            except Exception as e:
                corps = (f"<body style='background:#0d1117;color:#f85149;"
                         f"font-family:sans-serif;padding:40px'>"
                         f"<h2>Erreur de collecte</h2><pre>{e}</pre></body>").encode()
            ctype = "text/html; charset=utf-8"
        self._repondre(corps, ctype)

    def log_message(self, *a):
        pass


class _ServeurIPv6(socketserver.TCPServer):
    address_family = socket.AF_INET6
    allow_reuse_address = True


def _expliquer_port_occupe(port: int) -> None:
    """Message lisible plutot qu'une pile d'appels Python.

    On distingue deux cas tres differents : un tableau de bord deja lance
    (il suffit de l'ouvrir) et un autre programme sur le port (il faut en
    choisir un autre).
    """
    print(f"\nLe port {port} est deja occupe.\n", flush=True)

    deja_le_notre = False
    try:
        r = subprocess.run(["curl", "-s", "-m", "5", f"http://127.0.0.1:{port}/json"],
                           capture_output=True, text=True, timeout=10)
        deja_le_notre = '"rotation"' in r.stdout or '"nb_setups"' in r.stdout
    except Exception:
        pass

    if deja_le_notre:
        print("  C'est un tableau de bord deja en route — pas besoin d'en lancer un second.", flush=True)
        print(f"  Ouvre simplement : http://127.0.0.1:{port}\n", flush=True)
        print("  Pour le remplacer, arrete-le d'abord :", flush=True)
        print("    pkill -f gold_agent.web", flush=True)
    else:
        print("  Un autre programme utilise ce port. Deux options :\n", flush=True)
        print(f"    python3 -m gold_agent.web --port {port + 1}    # en choisir un autre", flush=True)
        print(f"    lsof -nP -iTCP:{port} -sTCP:LISTEN            # voir qui l'occupe", flush=True)
    print("", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(prog="gold_agent.web", description="Tableau de bord de l'or.")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--surveillance", type=int, default=300, metavar="SECONDES",
                    help="intervalle de surveillance en arriere-plan (0 = desactive, defaut 300)")
    ap.add_argument("--no-open", action="store_true", help="ne pas ouvrir le navigateur")
    a = ap.parse_args()

    arret = threading.Event()
    if a.surveillance > 0:
        tableau.definir_profil("surveillance")
        b = tableau.budget()
        print(f"Surveillance active — controle toutes les {a.surveillance}s", flush=True)
        c = notify.etat_canaux()
        print(f"  notification systeme  : {'oui' if c['systeme'] else 'NON'}", flush=True)
        print(f"  push telephone (ntfy) : {c['sujet'] or 'NON configure'}", flush=True)
        print(f"  volume en lots        : {'calcule' if c['capital_configure'] else 'CAPITAL absent de .env'}", flush=True)
        print(f"  cles Twelve Data : {b['cles']} en rotation — quota cumule {b['quota']}/jour", flush=True)
        print(f"  consommation prevue : ~{b['prevu']}/jour ({b['part_pct']}% du quota)", flush=True)
        print("  caches : " + ", ".join(f"{k}={v}s" for k, v in b["ttl"].items()), flush=True)
        threading.Thread(target=surveiller, args=(a.surveillance, arret), daemon=True).start()
    else:
        print("Surveillance desactivee (profil consultation, caches courts)", flush=True)

    socketserver.TCPServer.allow_reuse_address = True
    try:
        srv = socketserver.TCPServer(("127.0.0.1", a.port), Handler)
    except OSError as e:
        if e.errno != 48:      # EADDRINUSE
            raise
        arret.set()
        _expliquer_port_occupe(a.port)
        return 1

    # Deuxieme ecoute sur la boucle locale IPv6. Sur macOS, "localhost" resout
    # d'abord en ::1 : un serveur qui n'ecoute qu'en 127.0.0.1 est alors
    # injoignable quand on tape localhost dans le navigateur. On reste sur la
    # boucle locale — jamais sur toutes les interfaces, le tableau ne doit pas
    # etre expose au reseau.
    srv6 = None
    try:
        srv6 = _ServeurIPv6(("::1", a.port), Handler)
        threading.Thread(target=srv6.serve_forever, daemon=True).start()
    except OSError:
        pass   # pas d'IPv6 sur cette machine : 127.0.0.1 suffit

    with srv:
        url = f"http://127.0.0.1:{a.port}/"
        print(f"\nTableau de bord : {url}", flush=True)
        if srv6:
            print(f"          ou      http://localhost:{a.port}/   (IPv6 actif)", flush=True)
        if auth.comptes_existent():
            print(f"  acces protege : {len(auth.lister())} compte(s) — python3 -m gold_agent.auth lister", flush=True)
        else:
            print("  ACCES LIBRE — aucun compte defini. Pour proteger :", flush=True)
            print("    python3 -m gold_agent.auth ajouter <ton-nom>", flush=True)
        print("  /json pour les donnees brutes", flush=True)
        print("  Ctrl+C pour arreter", flush=True)
        if not a.no_open:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            arret.set()
            if srv6:
                srv6.shutdown()
            print(f"\narret — {ds.COMPTEUR['twelvedata']} requetes consommees cette session", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
