"""La decision du Superviseur — plus de blocages, une PROBABILITE.

Decision de Mushine (14/09) : le Miroir, l'Avocat, la Vigie et la
fiabilite du timeframe ne verrouillent plus les setups — ils PESENT,
composant par composant, dans une note 5-95 % affichee sur la carte et
conservee au journal. Verifiable, jamais opaque.
"""
from __future__ import annotations


def noter(st: dict, fiabilite: dict, suspension: str | None,
          miroir_contre: bool, verdict: dict | None) -> dict:
    """{pct, composantes} — la note du Superviseur pour un setup."""
    note, composantes = 50.0, []
    niveau_fi = (fiabilite or {}).get("niveau", "?")
    bonus_fi = {"mesuré": 20, "indicatif": 10, "déconseillé": -15,
                "non mesuré": -5}.get(niveau_fi, 0)
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
    return {"pct": int(max(5, min(95, round(note)))),
            "composantes": composantes}
