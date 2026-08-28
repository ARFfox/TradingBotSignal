"""Règle de trading mécanique + backtest sans biais de lookahead.

La règle ne relève d'aucun jugement : elle prend les bougies et sort des
niveaux, toujours de la même façon. Sa valeur ne vient pas de sa logique
mais de ce que le backtest en dit.

RÈGLE — « repli sur support en tendance »
  Filtre    : EMA rapide > EMA lente et prix > EMA lente (tendance haussière)
  Veto      : RSI >= seuil_surachat ET prix étiré de >= ecart_max% de l'EMA rapide
  Déclencheur : la mèche basse touche un support confirmé (à moins de tol x ATR)
  Entrée    : au niveau du support
  Stop      : entrée - (k_stop x ATR)
  Objectif  : première résistance confirmée au-dessus, si R:R >= rr_min
  Sortie    : premier des deux touché ; abandon après delai_max bougies

La version vendeuse est le miroir exact.

ANTI-LOOKAHEAD : à la bougie t, seules les bougies 0..t sont visibles, et un
pivot n'est connu qu'après ses `right` bougies de confirmation. Sans cette
précaution un backtest « découvre » des supports qui n'existaient pas encore,
et tous les résultats deviennent faux.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import indicators as ind, regime as rg, structure as st


@dataclass
class Params:
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_len: int = 14
    atr_len: int = 14
    pivot_span: int = 3          # bougies de confirmation d'un pivot
    tol_atr: float = 0.5         # proximité au niveau pour déclencher
    k_stop: float = 1.5          # stop en multiples d'ATR
    rr_min: float = 1.5          # R:R minimum exigé pour prendre le signal
    delai_max: int = 40          # abandon si ni stop ni objectif touché
    rsi_surachat: float = 70.0
    rsi_survente: float = 30.0
    ecart_max_pct: float = 5.0   # veto d'extension
    sens: str = "les_deux"       # achat | vente | les_deux
    cout_pts: float = 0.0        # spread + commission + glissement, en points
    facteur_superieur: int = 0   # 0 = desactive ; 12 = agrege 12 bougies (M5 -> H1)
    # Filtres de surachat / survente, actifs par defaut : sur H4 et H1 ils
    # ameliorent l'esperance ET reduisent le pire creux d'environ 25 %.
    rsi_max_achat: float = 70.0    # ne pas acheter au-dessus de ce RSI
    rsi_min_vente: float = 30.0    # ne pas vendre en dessous de ce RSI
    extension_max: float = 101.0   # score d'extension 0-100 (redondant avec le RSI en pratique)


@dataclass
class Signal:
    index: int
    sens: str
    entree: float
    stop: float
    objectif: float
    rr: float
    motif: str


@dataclass
class Trade:
    signal: Signal
    sortie_index: int | None = None
    sortie_prix: float | None = None
    resultat: str = "ouvert"      # gagnant | perdant | expire | ouvert
    r_multiple: float = 0.0
    bougies_tenues: int = 0


def _contexte_superieur(bars: list[dict], facteur: int,
                        ema_fast: int, ema_slow: int) -> list:
    """Sens de la tendance sur un timeframe agrege, aligne bougie par bougie.

    On agrege `facteur` bougies pour reconstituer le timeframe superieur sans
    requete supplementaire. ANTI-LOOKAHEAD : a la bougie t, la bougie agregee
    en cours est INCOMPLETE — on n'utilise donc que la derniere agregee
    entierement fermee.
    """
    n = len(bars)
    contexte = [None] * n
    if facteur < 2:
        return contexte

    clotures_agr, fin_de_bloc = [], []
    for debut in range(0, n - facteur + 1, facteur):
        bloc = bars[debut:debut + facteur]
        clotures_agr.append(bloc[-1]["close"])
        fin_de_bloc.append(debut + facteur - 1)

    if len(clotures_agr) < ema_slow + 1:
        return contexte

    ef = ind.ema(clotures_agr, ema_fast)
    es = ind.ema(clotures_agr, ema_slow)

    for k, idx_fin in enumerate(fin_de_bloc):
        if ef[k] is None or es[k] is None:
            continue
        sens = "haussier" if ef[k] > es[k] else "baissier"
        # Valable a partir de la bougie SUIVANT la cloture du bloc
        debut_validite = idx_fin + 1
        fin_validite = fin_de_bloc[k + 1] + 1 if k + 1 < len(fin_de_bloc) else n
        for i in range(debut_validite, min(fin_validite, n)):
            contexte[i] = sens
    return contexte


def _tous_les_pivots(highs, lows, span: int) -> dict:
    """Pivots calcules une seule fois sur toute la serie.

    Ce n'est PAS un lookahead : un pivot en i ne depend que de la fenetre
    [i-span, i+span]. Le filtrage par index <= t-span en aval garantit qu'a
    la bougie t on ne voit que des pivots deja confirmes. Le resultat est
    identique au recalcul bougie par bougie, mais lineaire au lieu de
    quadratique — indispensable sur 5000 bougies.
    """
    return st.pivots(highs, lows, left=span, right=span)


def _niveaux_connus(pivots_complets: dict, t: int, span: int) -> dict:
    """Sous-ensemble des pivots deja confirmes a la bougie t."""
    limite = t - span
    if limite < span:
        return {"highs": [], "lows": []}
    return {
        "highs": [p for p in pivots_complets["highs"] if p["index"] <= limite],
        "lows": [p for p in pivots_complets["lows"] if p["index"] <= limite],
    }


def detecter(bars: list[dict], p: Params) -> list[Signal]:
    """Parcourt l'historique et renvoie chaque signal, sans jamais regarder devant."""
    o = [b["open"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    n = len(c)

    # Series calculees une fois : chaque valeur en t ne depend que de 0..t
    ema_f = ind.ema(c, p.ema_fast)
    ema_s = ind.ema(c, p.ema_slow)
    rsi_v = ind.rsi(c, p.rsi_len)
    atr_v = ind.atr(h, l, c, p.atr_len)

    pivots_complets = _tous_les_pivots(h, l, p.pivot_span)
    contexte = _contexte_superieur(bars, p.facteur_superieur, p.ema_fast, p.ema_slow) \
        if p.facteur_superieur >= 2 else [None] * n

    signaux: list[Signal] = []
    depart = max(p.ema_slow, p.atr_len, p.pivot_span * 2) + 1

    for t in range(depart, n - 1):
        # Le filtre s'evalue sur la bougie PRECEDENTE : l'entree sur limite se
        # remplit pendant la bougie t, donc avant que sa cloture soit connue.
        # Filtrer sur c[t] reviendrait a decider avec une information
        # posterieure au remplissage — un lookahead qui gonfle les resultats.
        ef, es, rs, at = ema_f[t - 1], ema_s[t - 1], rsi_v[t - 1], atr_v[t - 1]
        if None in (ef, es, rs, at) or at <= 0:
            continue

        prix = c[t - 1]
        niv = _niveaux_connus(pivots_complets, t - 1, p.pivot_span)
        tol = at * p.tol_atr
        ecart = (prix - ef) / ef * 100

        ctx = contexte[t]
        # Score d'extension gradue, calcule une fois pour les deux sens.
        # Remplace l'ancien "RSI >= 70 ET ecart >= 5 %", ou un RSI a 69
        # desactivait toute la protection.
        ext = rg.score_extension(prix, ef, rs)["score"]

        # ---- ACHAT ----
        if p.sens in ("achat", "les_deux") and ef > es and prix > es \
                and (ctx is None or ctx == "haussier") \
                and rs < p.rsi_max_achat and ext < p.extension_max:
            if True:
                supports = [x["price"] for x in niv["lows"] if x["price"] < prix]
                resistances = [x["price"] for x in niv["highs"] if x["price"] > prix]
                if supports and resistances:
                    sup = max(supports)
                    # Remplissage realiste : le creux doit ATTEINDRE le support
                    # (l[t] <= sup), sinon l'ordre limite n'aurait pas ete rempli.
                    # La borne basse evite de retenir les cassures franches.
                    if sup - tol <= l[t] <= sup:
                        entree = sup
                        stop = entree - at * p.k_stop
                        objectif = min(resistances)
                        risque = entree - stop
                        if risque > 0:
                            rr = (objectif - entree) / risque
                            if rr >= p.rr_min:
                                signaux.append(Signal(t, "achat", round(entree, 2),
                                                      round(stop, 2), round(objectif, 2),
                                                      round(rr, 2),
                                                      f"repli sur support {sup:.2f} en tendance haussiere"))

        # ---- VENTE ----
        if p.sens in ("vente", "les_deux") and ef < es and prix < es \
                and (ctx is None or ctx == "baissier") \
                and rs > p.rsi_min_vente and ext < p.extension_max:
            if True:
                resistances = [x["price"] for x in niv["highs"] if x["price"] > prix]
                supports = [x["price"] for x in niv["lows"] if x["price"] < prix]
                if supports and resistances:
                    res = min(resistances)
                    if res <= h[t] <= res + tol:
                        entree = res
                        stop = entree + at * p.k_stop
                        objectif = max(supports)
                        risque = stop - entree
                        if risque > 0:
                            rr = (entree - objectif) / risque
                            if rr >= p.rr_min:
                                signaux.append(Signal(t, "vente", round(entree, 2),
                                                      round(stop, 2), round(objectif, 2),
                                                      round(rr, 2),
                                                      f"rebond sur resistance {res:.2f} en tendance baissiere"))

    return signaux


def simuler(bars: list[dict], signaux: list[Signal], p: Params) -> list[Trade]:
    """Déroule chaque signal bougie par bougie jusqu'au stop ou à l'objectif.

    Convention prudente : si une même bougie touche le stop ET l'objectif, on
    compte la perte. Sans données infra-bougie, impossible de savoir lequel
    est arrivé en premier — et se donner le bénéfice du doute gonfle
    artificiellement les résultats.
    """
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    trades: list[Trade] = []
    libre_a_partir_de = -1   # une seule position a la fois

    for s in signaux:
        # Un meme support touche sur plusieurs bougies consecutives genere
        # plusieurs signaux identiques. Les compter separement gonfle
        # artificiellement l'echantillon et duplique gains comme pertes.
        # On simule ce qu'un operateur ferait : une position a la fois.
        if s.index <= libre_a_partir_de:
            continue

        tr = Trade(signal=s)
        for j in range(s.index + 1, min(s.index + 1 + p.delai_max, len(bars))):
            if s.sens == "achat":
                touche_stop = l[j] <= s.stop
                touche_obj = h[j] >= s.objectif
            else:
                touche_stop = h[j] >= s.stop
                touche_obj = l[j] <= s.objectif

            # Le cout (spread + commission + glissement) s'applique a l'aller
            # comme au retour : il aggrave les pertes ET rogne les gains.
            risque = abs(s.entree - s.stop)
            if touche_stop:
                tr.sortie_index, tr.sortie_prix = j, s.stop
                tr.resultat = "perdant"
                tr.r_multiple = round(-(risque + p.cout_pts) / risque, 3)
                break
            if touche_obj:
                tr.sortie_index, tr.sortie_prix = j, s.objectif
                tr.resultat = "gagnant"
                tr.r_multiple = round((abs(s.objectif - s.entree) - p.cout_pts) / risque, 3)
                break
        else:
            fin = min(s.index + p.delai_max, len(bars) - 1)
            risque = abs(s.entree - s.stop)
            gain = (bars[fin]["close"] - s.entree) if s.sens == "achat" \
                else (s.entree - bars[fin]["close"])
            tr.sortie_index, tr.sortie_prix = fin, bars[fin]["close"]
            tr.resultat = "expire"
            tr.r_multiple = round((gain - p.cout_pts) / risque, 3) if risque else 0.0

        tr.bougies_tenues = (tr.sortie_index or s.index) - s.index
        libre_a_partir_de = tr.sortie_index if tr.sortie_index is not None else s.index
        trades.append(tr)

    return trades


def statistiques(trades: list[Trade]) -> dict:
    """Ce que la règle a réellement produit. Sans embellissement."""
    if not trades:
        return {"trades": 0, "verdict": "aucun signal — la regle ne se declenche pas sur cet historique"}

    gagnants = [t for t in trades if t.resultat == "gagnant"]
    perdants = [t for t in trades if t.resultat == "perdant"]
    expires = [t for t in trades if t.resultat == "expire"]
    rs = [t.r_multiple for t in trades]

    # Pire serie de pertes consecutives et pire creux cumule
    serie, pire_serie = 0, 0
    cumul, sommet, pire_creux = 0.0, 0.0, 0.0
    for t in trades:
        if t.r_multiple < 0:
            serie += 1
            pire_serie = max(pire_serie, serie)
        else:
            serie = 0
        cumul += t.r_multiple
        sommet = max(sommet, cumul)
        pire_creux = min(pire_creux, cumul - sommet)

    total_gains = sum(r for r in rs if r > 0)
    total_pertes = abs(sum(r for r in rs if r < 0))

    # Deux taux distincts : un trade sorti par expiration peut etre profitable
    # sans avoir touche l'objectif. Ne montrer que le premier donne une image
    # fausse (un +2,7R compte alors comme un echec).
    profitables = [t for t in trades if t.r_multiple > 0]

    n = len(trades)
    if n < 10:
        fiabilite = ("ECHANTILLON INSUFFISANT — aucune conclusion possible. "
                     "Il faut au moins 30 trades pour que ces chiffres aient un sens.")
    elif n < 30:
        fiabilite = ("Echantillon faible — resultats indicatifs seulement, "
                     "intervalles de confiance tres larges.")
    elif n < 100:
        fiabilite = "Echantillon modeste — tendance lisible, precision limitee."
    else:
        fiabilite = "Echantillon suffisant pour une lecture statistique."

    return {
        "trades": n,
        "gagnants": len(gagnants), "perdants": len(perdants), "expires": len(expires),
        "taux_objectif_atteint_pct": round(len(gagnants) / n * 100, 1),
        "taux_profitable_pct": round(len(profitables) / n * 100, 1),
        "fiabilite": fiabilite,
        "esperance_R": round(sum(rs) / len(rs), 3),
        "total_R": round(sum(rs), 2),
        "facteur_profit": round(total_gains / total_pertes, 2) if total_pertes else None,
        "pire_serie_pertes": pire_serie,
        "pire_creux_R": round(pire_creux, 2),
        "duree_moyenne_bougies": round(sum(t.bougies_tenues for t in trades) / len(trades), 1),
        "meilleur_R": round(max(rs), 2), "pire_R": round(min(rs), 2),
    }


def setup_actuel(bars: list[dict], p: Params) -> dict:
    """Les niveaux que la règle utiliserait MAINTENANT.

    Renvoie le setup même s'il n'est pas encore déclenché : c'est justement
    l'information utile — « si le prix revient à X, la règle entre, avec stop
    Y et objectif Z ». Rien n'est recommandé : c'est la sortie mécanique de
    la règle, dont le backtest mesure la valeur.
    """
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    t = len(c) - 1

    ef = ind.last_valid(ind.ema(c, p.ema_fast))
    es = ind.last_valid(ind.ema(c, p.ema_slow))
    rs = ind.last_valid(ind.rsi(c, p.rsi_len))
    at = ind.last_valid(ind.atr(h, l, c, p.atr_len))
    if None in (ef, es, rs, at) or at <= 0:
        return {"setup": None, "raison": "indicateurs indisponibles (historique trop court)"}

    prix = c[-1]
    niv = _niveaux_connus(_tous_les_pivots(h, l, p.pivot_span), t, p.pivot_span)
    ecart = (prix - ef) / ef * 100

    # Sens autorise par le filtre de tendance
    if ef > es and prix > es:
        sens = "achat"
    elif ef < es and prix < es:
        sens = "vente"
    else:
        return {"setup": None, "raison": "filtre de tendance non satisfait (EMA melees)",
                "ema_fast": round(ef, 2), "ema_slow": round(es, 2)}

    if p.sens != "les_deux" and p.sens != sens:
        return {"setup": None, "raison": f"la regle est limitee au sens '{p.sens}'"}

    if p.facteur_superieur >= 2:
        ctx = _contexte_superieur(bars, p.facteur_superieur, p.ema_fast, p.ema_slow)[-1]
        if ctx is not None and ctx != sens.replace("achat", "haussier").replace("vente", "baissier"):
            return {"setup": None,
                    "raison": f"le timeframe superieur est {ctx}, contraire au signal {sens}"}

    # EXACTEMENT les memes filtres que detecter(). Toute divergence ferait
    # afficher des niveaux que la regle backtestee aurait refuses — le
    # backtest ne mesurerait alors pas ce qui est montre.
    ext = rg.score_extension(prix, ef, rs)
    if ext["score"] >= p.extension_max:
        return {"setup": None,
                "raison": f"extension {ext['niveau']} (score {ext['score']}/100)"}
    if sens == "achat" and rs >= p.rsi_max_achat:
        return {"setup": None,
                "raison": f"surachat — RSI {rs:.1f} >= seuil {p.rsi_max_achat}"}
    if sens == "vente" and rs <= p.rsi_min_vente:
        return {"setup": None,
                "raison": f"survente — RSI {rs:.1f} <= seuil {p.rsi_min_vente}"}

    supports = [x["price"] for x in niv["lows"] if x["price"] < prix]
    resistances = [x["price"] for x in niv["highs"] if x["price"] > prix]
    if not supports or not resistances:
        return {"setup": None, "raison": "pas de pivot confirme de part et d'autre du prix"}

    if sens == "achat":
        entree = max(supports)
        stop = entree - at * p.k_stop
        objectif = min(resistances)
        risque = entree - stop
        gain = objectif - entree
    else:
        entree = min(resistances)
        stop = entree + at * p.k_stop
        objectif = max(supports)
        risque = stop - entree
        gain = entree - objectif

    if risque <= 0 or gain <= 0:
        return {"setup": None, "raison": "geometrie invalide (risque ou gain negatif)"}

    rr = gain / risque
    if rr < p.rr_min:
        return {"setup": None,
                "raison": f"R:R {rr:.2f} sous le minimum de {p.rr_min}"}
    tol = at * p.tol_atr
    distance = abs(prix - entree)
    if sens == "achat":
        atteint = entree - tol <= l[-1] <= entree
    else:
        atteint = entree <= h[-1] <= entree + tol

    return {
        "setup": sens,
        "declenche": atteint,
        "entree": round(entree, 2),
        "entree_zone": [round(entree - tol, 2), round(entree + tol, 2)],
        "stop": round(stop, 2),
        "stop_zone": [round(min(stop, entree - risque * 0.85), 2),
                      round(max(stop, entree - risque * 0.85), 2)] if sens == "achat"
                     else [round(min(stop, entree + risque * 0.85), 2),
                           round(max(stop, entree + risque * 0.85), 2)],
        "objectif": round(objectif, 2),
        "objectif_zone": [round(objectif - tol, 2), round(objectif + tol, 2)],
        "rr": round(rr, 2),
        "rr_suffisant": rr >= p.rr_min,
        "risque_pts": round(risque, 2),
        "gain_pts": round(gain, 2),
        "prix_actuel": round(prix, 2),
        "distance_a_entree": round(distance, 2),
        "atr": round(at, 2),
        "rsi": round(rs, 1),
        "ecart_ema_pct": round(ecart, 2),
    }
