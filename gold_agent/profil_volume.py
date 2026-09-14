"""Profil de volume — POC, VAH/VAL, HVN/LVN (skill strategies-entree §4).

Approximation assumee : le poids de chaque bougie est reparti UNIFORMEMENT
sur son range. Le vrai profil demande des ticks ; sur H1 et au-dessus,
l'ecart n'a jamais change un POC de niveau dans les essais du corpus. Sur
M5, ne pas s'y fier.

⚠️ L'or spot n'a PAS de volume chez Twelve Data (0 partout). Dans ce cas
le profil se replie sur un poids de 1 par bougie — un profil de TEMPS
(time-at-price), pas de volume — et le dit : `source_poids` vaut "temps".
Faire semblant qu'un zero est un volume serait un mensonge de donnees.
"""
from __future__ import annotations

PART_ZONE_VALEUR = 0.70     # VAH/VAL : les 70 % centraux du poids
SEUIL_HVN = 1.5             # x la mediane des niveaux occupes
SEUIL_LVN = 0.5


def profil_volume(bars: list[dict], n_niveaux: int = 50) -> dict | None:
    """{"poc","vah","val","hvn":[...],"lvn":[...],"source_poids"} ou None."""
    if len(bars) < 20 or n_niveaux < 5:
        return None
    bas = min(b["low"] for b in bars)
    haut = max(b["high"] for b in bars)
    if haut <= bas:
        return None
    pas = (haut - bas) / n_niveaux

    a_du_volume = any((b.get("volume") or 0) > 0 for b in bars)
    histo = [0.0] * n_niveaux
    for b in bars:
        poids = (b.get("volume") or 0.0) if a_du_volume else 1.0
        if poids <= 0:
            continue
        i0 = int((b["low"] - bas) / pas)
        i1 = int((b["high"] - bas) / pas)
        i0 = max(0, min(n_niveaux - 1, i0))
        i1 = max(0, min(n_niveaux - 1, i1))
        part = poids / (i1 - i0 + 1)
        for i in range(i0, i1 + 1):
            histo[i] += part

    total = sum(histo)
    if total <= 0:
        return None
    prix_niveau = [bas + (i + 0.5) * pas for i in range(n_niveaux)]

    i_poc = max(range(n_niveaux), key=lambda i: histo[i])

    # Zone de valeur : on part du POC et on etend du cote qui ajoute le
    # plus de poids, jusqu'a couvrir 70 % du total (methode standard).
    lo = hi = i_poc
    cumul = histo[i_poc]
    while cumul < PART_ZONE_VALEUR * total and (lo > 0 or hi < n_niveaux - 1):
        gauche = histo[lo - 1] if lo > 0 else -1.0
        droite = histo[hi + 1] if hi < n_niveaux - 1 else -1.0
        if droite >= gauche:
            hi += 1
            cumul += histo[hi]
        else:
            lo -= 1
            cumul += histo[lo]

    occupes = sorted(v for v in histo if v > 0)
    mediane = occupes[len(occupes) // 2] if occupes else 0.0
    hvn = [prix_niveau[i] for i in range(n_niveaux)
           if mediane and histo[i] >= SEUIL_HVN * mediane]
    lvn = [prix_niveau[i] for i in range(n_niveaux)
           if histo[i] > 0 and mediane and histo[i] <= SEUIL_LVN * mediane]

    return {"poc": round(prix_niveau[i_poc], 6),
            "vah": round(prix_niveau[hi], 6),
            "val": round(prix_niveau[lo], 6),
            "hvn": [round(x, 6) for x in hvn],
            "lvn": [round(x, 6) for x in lvn],
            "pas": round(pas, 6),
            "source_poids": "volume" if a_du_volume else "temps"}


def dans_lvn(prix: float, profil: dict) -> bool:
    """Un objectif place dans un LVN ne se remplit pas : le prix y passe
    sans s'arreter (la regle la plus utile du corpus)."""
    demi = profil["pas"] / 2
    return any(abs(prix - n) <= demi for n in profil.get("lvn", []))
