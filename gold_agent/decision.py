"""La decision du Superviseur — une PROBABILITE qui APPREND de l'historique.

Decision de Mushine (14/09) : plus de blocages — le Miroir, l'Avocat, la
Vigie et la fiabilite pesent dans une note 5-95 %. Et le Superviseur
S'AUTO-CALIBRE : a chaque collecte, il relit le journal reel et les poids
Brier mesures des agents, et ajuste la note AUTOMATIQUEMENT :

- un timeframe qui perd en live (journal 90 j) voit ses notes descendre ;
  un timeframe qui gagne les voit monter — sans intervention ;
- un agent dont les avis se verifient (>= 10 avis resolus) pese de plus
  en plus ; un agent qui se trompe pese de moins en moins (Brier) ;
- seules les opportunites PROPRES (note >= SEUIL_NOTIFICATION) partent au
  telephone — tout reste visible et journalise sur le site.

Chaque composante est AFFICHEE : une note qu'on ne peut pas decomposer
serait un chiffre de marketing.
"""
from __future__ import annotations

SEUIL_NOTIFICATION = 55     # en-dessous : visible sur le site, pas de push
JOURNAL_TRADES_MIN = 5      # le vecu d'un TF ne pese qu'a partir de 5 resolus
BRIER_PLAFOND = 15          # la calibration pese au plus ±15 points


def _composante_journal(carreau: dict | None) -> tuple[int, str | None]:
    """Le vecu LIVE du timeframe (fenetre 90 j) : taux et esperance reels."""
    if not carreau or carreau.get("trades", 0) < JOURNAL_TRADES_MIN:
        return 0, None
    n = carreau["trades"]
    taux = carreau.get("taux_reussite") or 0.0
    r_moyen = (carreau.get("r_cumule") or 0.0) / n
    delta = int(max(-20, min(20, round((taux - 50) * 0.4 + r_moyen * 10))))
    if not delta:
        return 0, None
    return delta, f"journal {n}t/{taux:.0f}% {delta:+d}"


def _composante_brier(st: dict, calibration: dict | None,
                      tf: str) -> tuple[int, str | None]:
    """Les agents CALIBRES votent : d'accord avec le sens = +poids,
    contre = -poids. Sans poids calcule (< 10 avis resolus), silence."""
    avis = st.get("avis") or {}
    sens = st.get("setup")
    if not avis or not calibration or sens not in ("achat", "vente"):
        return 0, None
    total, votants = 0.0, 0
    for code, direction in avis.items():
        c = calibration.get(code) or {}
        cellule = (c.get("par_tf") or {}).get(tf) or c.get("global") or {}
        poids = cellule.get("poids")
        if poids is None:
            continue
        votants += 1
        total += poids if direction == sens else -poids
    if not votants:
        return 0, None
    delta = int(max(-BRIER_PLAFOND, min(BRIER_PLAFOND, round(total * 12))))
    if not delta:
        return 0, None
    return delta, f"Brier {votants} agent(s) calibré(s) {delta:+d}"


def noter(st: dict, fiabilite: dict, suspension: str | None,
          miroir_contre: bool, verdict: dict | None,
          carreau: dict | None = None,
          calibration: dict | None = None) -> dict:
    """{pct, composantes, notifiable} — la note du Superviseur."""
    note, composantes = 50.0, []

    niveau_fi = (fiabilite or {}).get("niveau", "?")
    bonus_fi = {"mesuré": 20, "indicatif": 10, "déconseillé": -15,
                "non mesuré": -5,
                # multi-marches : le verdict du protocole note l'instrument
                "walk-forward autorisé": 15,
                "walk-forward REFUSÉ": -20}.get(niveau_fi, 0)
    if bonus_fi:
        note += bonus_fi
        composantes.append(f"fiabilité {niveau_fi} {bonus_fi:+d}")

    im = st.get("intermarche")
    if im and im.get("facteur") is not None:
        delta = round((im["facteur"] - 1.0) * 40)
        if miroir_contre:
            delta = min(delta, -20)
        if delta:
            note += delta
            composantes.append(f"Miroir ×{im['facteur']:.2f} {delta:+d}")

    if verdict:
        maj = sum(1 for o in verdict["objections"]
                  if o["gravite"] == "majeure" and not o["refutee"])
        mine = sum(1 for o in verdict["objections"]
                   if o["gravite"] != "majeure" or o["refutee"])
        if maj or mine:
            delta = -15 * maj - 4 * mine
            note += delta
            composantes.append(f"Avocat {maj} majeure(s)/{mine} autre(s) {delta:+d}")

    if suspension:
        note -= 15
        composantes.append(f"vigilance ({suspension[:40]}…) -15")

    # --- auto-calibration : l'historique reel ajuste la note --------------
    d_j, t_j = _composante_journal(carreau)
    if t_j:
        note += d_j
        composantes.append(t_j)
    d_b, t_b = _composante_brier(st, calibration,
                                 (carreau or {}).get("tf", ""))
    if t_b:
        note += d_b
        composantes.append(t_b)

    pct = int(max(5, min(95, round(note))))
    return {"pct": pct, "composantes": composantes,
            "notifiable": pct >= SEUIL_NOTIFICATION}
