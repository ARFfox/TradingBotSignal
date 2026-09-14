"""Les boucles permanentes — le contrat d'agent de la spec (§6).

Regles non negociables :
- une boucle qui plante REDEMARRE SEULE, avec backoff exponentiel
  (2, 4, 8... 300 s max) — elle ne fait jamais tomber les autres ;
- chaque tour reussi pose un BATTEMENT DE COEUR ; une boucle sans
  battement depuis 3 x son intervalle est declaree MORTE et signalee
  dans l'interface (jamais masquee) ;
- une boucle ne decide de rien : elle fait tourner la collecte et les
  notifications, les verdicts restent ou ils sont.

C'est ce qui rend le systeme reellement « toujours en ligne » : la
collecte, la resolution du journal, la calibration et le rapport
quotidien continuent MEME SANS NAVIGATEUR OUVERT.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

BACKOFF_MAX = 300
FACTEUR_MORT = 3        # sans battement depuis 3 x intervalle -> morte


@dataclass
class Boucle:
    code: str
    nom: str
    intervalle: float           # secondes entre deux tours
    fonction: object            # callable() -> None, un TOUR de travail
    heartbeat: float = 0.0
    tours: int = 0
    erreurs_consecutives: int = 0
    derniere_erreur: str = ""
    derniere_duree_ms: float = 0.0

    def tour(self) -> None:
        d0 = time.perf_counter()
        self.fonction()
        self.derniere_duree_ms = round((time.perf_counter() - d0) * 1000, 1)
        self.heartbeat = time.time()
        self.tours += 1
        self.erreurs_consecutives = 0
        self.derniere_erreur = ""

    def vivante(self, maintenant: float | None = None) -> bool:
        if not self.heartbeat:
            return False
        return ((maintenant or time.time()) - self.heartbeat
                < FACTEUR_MORT * self.intervalle)


_ETAT = {"boucles": [], "demarre": False, "verrou": threading.Lock()}


def _courir(b: Boucle, arret: threading.Event) -> None:
    while not arret.is_set():
        try:
            b.tour()
            attente = b.intervalle
        except Exception as e:
            b.erreurs_consecutives += 1
            b.derniere_erreur = str(e)[:140]
            attente = min(BACKOFF_MAX, 2 ** b.erreurs_consecutives)
        arret.wait(attente)


def demarrer(boucles: list[Boucle], arret: threading.Event) -> list[Boucle]:
    """Lance chaque boucle dans son propre fil. Idempotent : un second
    appel ne double pas les fils."""
    with _ETAT["verrou"]:
        if _ETAT["demarre"]:
            return _ETAT["boucles"]
        _ETAT["boucles"] = boucles
        _ETAT["demarre"] = True
    for b in boucles:
        threading.Thread(target=_courir, args=(b, arret),
                         daemon=True, name=f"boucle-{b.code}").start()
    return boucles


def etat() -> list[dict]:
    """L'etat de chaque boucle — pour la sante, l'API et le rapport."""
    maintenant = time.time()
    out = []
    for b in _ETAT["boucles"]:
        age = round(maintenant - b.heartbeat, 1) if b.heartbeat else None
        out.append({"code": b.code, "nom": b.nom,
                    "intervalle": b.intervalle, "tours": b.tours,
                    "battement_age_s": age,
                    "vivante": b.vivante(maintenant),
                    "erreurs_consecutives": b.erreurs_consecutives,
                    "derniere_erreur": b.derniere_erreur,
                    "derniere_duree_ms": b.derniere_duree_ms})
    return out


# --------------------------------------------------------------------------
# Les boucles du serveur
# --------------------------------------------------------------------------
class EtapeSignaux:
    """Un TOUR de la surveillance des signaux : collecte + notification des
    nouveaux (l'ancienne boucle `surveiller`, decoupee en pas pour recevoir
    battement et backoff). Amorce sans notifier : un signal deja present au
    demarrage declencherait une alerte trompeuse."""

    def __init__(self):
        self.connus: set = set()
        self.premier = True

    def __call__(self) -> None:
        from datetime import datetime
        from . import notify, tableau
        from .graphique import _grand_graphique
        from .rendu import _cle_signal

        d = tableau.collecter()
        actuels = set()
        for r in d["timeframes"]:
            s = r.get("setup") or {}
            if not s.get("setup") or s.get("suspendu"):
                continue
            cle = _cle_signal(r)
            actuels.add(cle)
            if self.premier or cle in self.connus:
                continue
            fi = (r.get("fiabilite") or {}).get("niveau", "?")
            try:
                svg = _grand_graphique(r)
            except Exception:
                svg = None
            envoye = notify.diffuser(r["nom"], s, d.get("prix"), fi, svg=svg)
            canaux = ", ".join(k for k, v in envoye.items() if v) or "aucun canal"
            print(f"[{datetime.now():%H:%M:%S}] signal {r['nom']} {s['setup']} "
                  f"entree {s['entree']} (fiabilite: {fi}) -> {canaux}", flush=True)
        self.connus = actuels
        self.premier = False


def _tour_collecte() -> None:
    from . import tableau
    tableau.collecter()


def defaut(intervalle_signaux: int = 300) -> list[Boucle]:
    """Les boucles du serveur. La collecte tourne plus souvent que la
    notification : c'est elle qui resout le journal, nourrit la calibration
    et ecrit le rapport quotidien — les TTL par bougie bornent son cout."""
    return [
        Boucle("collecte", "Collecte & résolution", 60.0, _tour_collecte),
        Boucle("signaux", "Surveillance des signaux",
               float(intervalle_signaux), EtapeSignaux()),
    ]
