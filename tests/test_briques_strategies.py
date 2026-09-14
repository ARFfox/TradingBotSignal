"""Tests des briques du skill strategies-entree — sans reseau.

Invariants proteges :
- le profil dit sa source de poids : "volume" quand il y en a, "temps"
  sinon (l'or spot n'a pas de volume — faire semblant serait mentir)
- le POC tombe la ou le poids se concentre ; VAL <= POC <= VAH
- un TP dans un LVN est detectable (la regle la plus utile du corpus)
- le VWAP est tire vers les bougies a fort volume
- les sessions REFUSENT le crypto (24/7 : une session y serait arbitraire)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import profil_volume as pv, sessions


def _bar(t, px, vol=0.0, ampli=1.0):
    return {"time": t, "open": px, "high": px + ampli, "low": px - ampli,
            "close": px, "volume": vol}


def test_poc_au_centre_de_gravite_du_volume():
    # 30 bougies autour de 100, mais tout le volume autour de 110
    bars = ([_bar(i, 100.0, vol=1.0) for i in range(30)]
            + [_bar(30 + i, 110.0, vol=50.0) for i in range(10)])
    p = pv.profil_volume(bars, n_niveaux=40)
    assert p["source_poids"] == "volume"
    assert abs(p["poc"] - 110.0) < 1.5, f"POC {p['poc']} loin du volume"
    assert p["val"] <= p["poc"] <= p["vah"]


def test_sans_volume_le_profil_se_dit_temporel():
    bars = [_bar(i, 100.0 + (i % 5)) for i in range(40)]     # volume 0 partout
    p = pv.profil_volume(bars, n_niveaux=30)
    assert p["source_poids"] == "temps"


def test_un_tp_dans_un_lvn_est_detecte():
    # un noeud dense a 100, un niveau quasi vide a 120 (une seule bougie fine)
    bars = ([_bar(i, 100.0, vol=10.0) for i in range(50)]
            + [_bar(50, 120.0, vol=0.5, ampli=0.4)])
    p = pv.profil_volume(bars, n_niveaux=40)
    assert p["lvn"], "aucun LVN detecte sur un profil pourtant troue"
    niveau_creux = min(p["lvn"], key=lambda x: abs(x - 120.0))
    assert pv.dans_lvn(niveau_creux, p)
    assert not pv.dans_lvn(p["poc"], p), "le POC n'est jamais un LVN"


def test_vwap_tire_par_le_volume():
    bars = [_bar(0, 100.0, vol=1.0), _bar(1, 200.0, vol=99.0)]
    v, source = sessions.vwap(bars)
    assert source == "volume" and v > 190, "le VWAP doit coller au gros volume"
    v2, source2 = sessions.vwap([_bar(0, 100.0), _bar(1, 200.0)])
    assert source2 == "temps" and abs(v2 - 150.0) < 1


def test_les_sessions_refusent_le_crypto():
    with pytest.raises(ValueError):
        sessions.session_active(1700000000, marche="crypto")
    with pytest.raises(ValueError):
        sessions.range_asiatique([], marche="crypto")


def test_session_active_et_chevauchement():
    import datetime as dt
    def ts(h):
        return int(dt.datetime(2026, 9, 14, h, 30,
                               tzinfo=dt.timezone.utc).timestamp())
    assert sessions.session_active(ts(3)) == "asie"
    assert sessions.session_active(ts(9)) == "londres"
    assert sessions.session_active(ts(14)) == "chevauchement"
    assert sessions.session_active(ts(18)) == "ny"
    assert sessions.session_active(ts(22)) == "creux"


def test_range_asiatique_et_balayage():
    import datetime as dt
    base = dt.datetime(2026, 9, 14, 0, 0, tzinfo=dt.timezone.utc)
    bars = []
    for h in range(0, 8):        # asie : range 99-103
        t = int((base + dt.timedelta(hours=h)).timestamp())
        bars.append({"time": t, "open": 100, "high": 103, "low": 99,
                     "close": 101, "volume": 0})
    t = int((base + dt.timedelta(hours=9)).timestamp())
    bars.append({"time": t, "open": 101, "high": 104.5, "low": 100,
                 "close": 102, "volume": 0})     # Londres balaye le haut
    b = sessions.balayage_asiatique(bars)
    assert b["haut"] == 103 and b["bas"] == 99
    assert b["balaye"] and b["cote"] == "haut"


def test_flux_crypto_lit_le_positionnement():
    """AG-05 : lecture de positionnement, jamais un vote au consensus."""
    from gold_agent import flux

    class Fake:
        def funding(self, s): return {"taux_pct": 0.05, "prochain_ts": 0}
        def open_interest(self, s): return {"actuel": 104.0,
                                            "variation_pct": 4.0, "heures": 24}
        def ratio_long_short(self, s): return {"ratio": 2.2, "part_long_pct": 68.8}

    out = flux.flux_crypto(feed=Fake())
    assert out["disponible"] and out["ratio_ls"] == 2.2
    texte = " ".join(out["lecture"])
    assert "longs payent cher" in texte, "funding 0,05 %/8h = charge"
    assert "consensus acheteur chargé" in texte, "ratio 2,2 = longs charges"
    assert "l'argent entre" in texte

    class Panne:
        def funding(self, s): raise OSError("reseau")
        def open_interest(self, s): raise OSError("reseau")
        def ratio_long_short(self, s): raise OSError("reseau")
    out2 = flux.flux_crypto(feed=Panne())
    assert out2["disponible"] is False, "panne = indisponible, jamais d'exception"
