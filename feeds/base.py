"""Le contrat que respecte CHAQUE source de donnees (regle 15 du SYSTEME :
aucun acces direct a une API — toujours via un adapter d'ici).

Ce que la classe de base fournit, pour que chaque adapter ne l'ecrive pas
a sa facon :
- un SEAU A JETONS par source : le rate limit est respecte par construction,
  pas par prudence ;
- un BACKOFF exponentiel : une erreur reseau se retente en 1, 2, 4 s —
  jamais en rafale ;
- un CACHE disque par (source, symbole, tf) : deux appels dans la meme
  minute ne coutent qu'une requete ;
- la VALIDATION : bougies normalisees {time, open, high, low, close,
  volume}, floats, ordre chronologique strict — le format exact que
  strategy.py et walkforward.py consomment deja.

Chaque adapter n'implemente QUE `_fetch(symbole, tf, nombre)` et declare
son rythme. Les tests mockent `_transport` : jamais d'appel reseau dans un
test (regle 18).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

DOSSIER_CACHE = Path.home() / ".gold_feeds"

# Duree de vie du cache par timeframe : calee sur la bougie, comme le
# tableau. Une bougie 1 h ne change pas de nature toutes les 10 secondes.
TTL_PAR_TF = {"D": 6 * 3600, "240": 1800, "60": 900, "30": 600,
              "15": 300, "5": 120}


class SeauJetons:
    """Rate limit par construction : `prendre()` bloque si le seau est vide.

    L'horloge et le sommeil sont injectables pour tester sans attendre.
    """

    def __init__(self, capacite: int, recharge_par_s: float,
                 horloge=time.monotonic, sommeil=time.sleep):
        self.capacite = float(capacite)
        self.recharge = float(recharge_par_s)
        self.jetons = float(capacite)
        self.derniere = horloge()
        self.horloge = horloge
        self.sommeil = sommeil

    def prendre(self, n: float = 1.0) -> float:
        """Consomme n jetons ; retourne le temps attendu (0 si aucun)."""
        attendu = 0.0
        while True:
            maintenant = self.horloge()
            self.jetons = min(self.capacite,
                              self.jetons + (maintenant - self.derniere) * self.recharge)
            self.derniere = maintenant
            if self.jetons >= n:
                self.jetons -= n
                return attendu
            manque = (n - self.jetons) / self.recharge
            self.sommeil(manque)
            attendu += manque


def valider_bars(bars: list[dict]) -> list[dict]:
    """Normalise et verifie : floats, champs presents, ordre chronologique.

    Une bougie invalide est JETEE (pas corrigee en silence) ; un desordre
    temporel est corrige par tri — c'est une propriete, pas une opinion.
    """
    propres = []
    for b in bars:
        try:
            o, h, l, c = (float(b["open"]), float(b["high"]),
                          float(b["low"]), float(b["close"]))
            t = int(b["time"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (l <= min(o, c) + 1e-9 and h >= max(o, c) - 1e-9):
            continue                      # bougie incoherente : on la jette
        propres.append({"time": t, "open": o, "high": h, "low": l, "close": c,
                        "volume": float(b.get("volume") or 0.0)})
    propres.sort(key=lambda b: b["time"])
    # doublons de timestamp : garder la derniere version
    dedup = {}
    for b in propres:
        dedup[b["time"]] = b
    return list(dedup.values())


class Feed:
    """Classe de base. Un adapter definit `nom`, son seau, et `_fetch`."""

    nom = "?"

    def __init__(self, seau: SeauJetons | None = None,
                 sommeil=time.sleep):
        self.seau = seau or SeauJetons(10, 2.0)
        self.sommeil = sommeil

    # -- transport -----------------------------------------------------------
    def _transport(self, url: str, timeout: int = 20):
        """Le SEUL point qui touche le reseau — c'est lui que les tests
        remplacent par des reponses figees.

        curl plutot qu'urllib : la chaine de certificats de ce Mac fait
        echouer urllib (certificat auto-signe) alors que curl passe — c'est
        deja la solution eprouvee de news._curl_json.
        """
        import subprocess
        p = subprocess.run(["curl", "-s", "-m", str(timeout),
                            "-A", "gold-agent/1.0", url],
                           capture_output=True, text=True, timeout=timeout + 10)
        if not p.stdout.strip():
            raise RuntimeError("reponse vide")
        return json.loads(p.stdout)

    def _requete(self, url: str, essais: int = 4):
        """Seau a jetons + backoff exponentiel (1, 2, 4 s)."""
        derniere = None
        for k in range(essais):
            self.seau.prendre()
            try:
                return self._transport(url)
            except Exception as e:          # reseau, HTTP, JSON — meme remede
                derniere = e
                if k < essais - 1:
                    self.sommeil(2 ** k)
        raise RuntimeError(f"{self.nom} : {derniere}")

    # -- cache ---------------------------------------------------------------
    def _chemin_cache(self, symbole: str, tf: str) -> Path:
        sur = symbole.replace("/", "_").replace("=", "_").replace("^", "_")
        return DOSSIER_CACHE / f"{self.nom}_{sur}_{tf}.json"

    # -- API publique --------------------------------------------------------
    def bars(self, symbole: str, tf: str, nombre: int = 1000,
             ttl: int | None = None) -> list[dict]:
        """Bougies normalisees, du cache si assez fraiches."""
        ttl = TTL_PAR_TF.get(tf, 600) if ttl is None else ttl
        chemin = self._chemin_cache(symbole, tf)
        try:
            if chemin.exists() and time.time() - chemin.stat().st_mtime < ttl:
                brut = json.loads(chemin.read_text())
                # Nouveau format {demande, bars} ; l'ancien etait une liste.
                donnees = brut.get("bars", []) if isinstance(brut, dict) else brut
                demande = brut.get("demande", len(donnees)) if isinstance(brut, dict) else len(donnees)
                # Le cache ne repond que s'il couvre la taille demandee : un
                # cache de 50 bougies ne doit JAMAIS repondre a une demande
                # de 5000 (bug reel : un petit appel d'essai avait fige le
                # cache et le walk-forward recevait 50 bougies).
                if donnees and (len(donnees) >= nombre or demande >= nombre):
                    return donnees[-nombre:]
        except Exception:
            pass
        propres = valider_bars(self._fetch(symbole, tf, nombre))
        if propres:
            try:
                DOSSIER_CACHE.mkdir(exist_ok=True)
                chemin.write_text(json.dumps({"demande": nombre, "bars": propres}))
            except Exception:
                pass
        return propres[-nombre:]

    def _fetch(self, symbole: str, tf: str, nombre: int) -> list[dict]:
        raise NotImplementedError
