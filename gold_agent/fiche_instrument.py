"""La fiche instrument du site — maquette.html est la référence (8.7).

TOUS les calculs vivent dans `vue_instrument.py` (module livré, 29 tests) :
ce fichier ne fait que l'adaptation (journal → Signal, actifs normalisés)
et le rendu HTML. Deux blocs :

- `bloc_haut`  : bandeau de 4 tuiles (R cumulé en héros, JAUGE taux contre
  équilibre, pips nets, résolus/émis) + les 6 boutons timeframe pleine
  largeur (verdict + effectif, coupé atténué mais cliquable) ;
- `bloc_bas`   : onglets Signaux validés | Historique complet | Risque,
  tableaux à 5 lignes visibles puis défilement.

Le SIGNE et l'icône portent le sens partout — le rouge et le vert sont
indistinguables en deutéranopie (~8 % des hommes).
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

VERDICT_CLS = {"AUTORISÉ": "autorise", "COUPÉ": "coupe",
               "OBSERVATION": "obs", "INSUFFISANT": "insuf"}


def _actifs() -> list[dict]:
    """Les signaux EN COURS, normalisés sur le SYMBOLE (le journal parle en
    symboles, les pastilles du site en clés)."""
    out = []
    try:
        from . import tableau
        for s in ((getattr(tableau, "DERNIER_PAQUET", None) or {})
                  .get("signaux_actifs") or []):
            out.append({"instrument": s.get("libelle") or s.get("instrument"),
                        "tf": s.get("tf"), "marche": s.get("marche")})
    except Exception:
        pass
    if not out:
        try:
            from . import multi
            for s in multi.signaux_actifs_multi():
                out.append({"instrument": s.get("libelle"), "tf": s.get("tf"),
                            "marche": s.get("marche")})
        except Exception:
            pass
    return out


def _fiche(cle: str):
    from vue_instrument import fiche
    from . import instruments
    from .apprentissage import signaux
    inst = instruments.par_cle(cle)
    f = fiche(signaux(), inst.symbole, _actifs())
    f.marche = inst.marche
    return inst, f


def json_fiche(cle: str) -> dict:
    """La route /api/instrument/<cle> — contrat APPLIQUER §8.2, plus les
    deux blocs HTML prêts à insérer (une seule source de calcul)."""
    inst, f = _fiche(cle)
    g = f.global_
    return {
        "instrument": f.instrument, "nom": inst.nom, "marche": f.marche,
        "badge": f.badge, "tf_signal": f.tf_avec_signal,
        "sous_hasard": f.sous_le_hasard,
        "global": {"texte": g.texte_taux, "taux": g.taux, "n": g.n_resolus,
                   "r_total": round(g.r_total, 2),
                   "pips_net": round(g.pips_net), "hasard": round(g.hasard, 3),
                   "n_attente": g.n_attente, "n_expire": g.n_expire},
        "timeframes": [
            {"tf": tf, "n": c.n_resolus, "taux": c.taux, "ic": c.ic,
             "r_moyen": c.r_moyen, "pips": round(c.pips_net),
             "verdict": c.verdict, "signal": tf in f.tf_avec_signal,
             "texte": c.texte_taux}
            for tf, c in f.timeframes.items()],
        "historique": [{
            "cree_le": s.cree_ts, "tf": s.tf, "sens": s.sens,
            "entree": s.entree, "sl": s.sl, "tp": s.tp, "statut": s.statut,
            "r": s.r_realise} for s in f.signaux[:200]],
        "html_haut": bloc_haut(cle, _deja=(inst, f)),
        "html_bas": bloc_bas(cle, _deja=(inst, f)),
    }


def _signe(v, decimales=0, suffixe="") -> str:
    """« +1.66 » / « −1 344 » — le signe TOUJOURS, la couleur accompagne."""
    if v is None:
        return "—"
    cls = "pos" if v > 0 else ("neg" if v < 0 else "")
    coul = f' style="color:var(--{"gain" if v > 0 else "perte"});font-weight:650"' if v else ""
    n = f"{abs(v):,.{decimales}f}".replace(",", " ")
    return f'<span class="mono"{coul}>{"+" if v > 0 else "−" if v < 0 else ""}{n}{suffixe}</span>'


def bloc_haut(cle: str, _deja=None) -> str:
    """Bandeau 4 tuiles + rangée des 6 timeframes (maquette)."""
    inst, f = _deja or _fiche(cle)
    g = f.global_
    h = ['<div class="stats4">']

    # 1. LE chiffre héros : le R cumulé — la mesure qui décide.
    cls_r = "neg" if g.r_total < 0 else ("pos" if g.r_total > 0 else "")
    r_txt = f"{'−' if g.r_total < 0 else '+' if g.r_total > 0 else ''}{abs(g.r_total):.1f}"
    h.append(f'<div class="tuile"><div class="lab">R cumulé — {f.instrument}</div>'
             f'<div class="heros {cls_r} mono">{r_txt} R</div>'
             f'<div class="sous">la mesure qui compte · {g.n_resolus} résolus</div></div>')

    # 2. LA JAUGE : taux mesuré CONTRE l'équilibre — deux nombres qui ne
    # veulent rien dire séparément. Échelle ×2 (0–50 %), comme la maquette.
    if g.taux is not None:
        taux_pct = g.taux * 100
        equi = g.hasard * 100
        rempli = min(100, taux_pct * 2)
        seuil = min(96, equi * 2)
        ok = " ok" if taux_pct >= equi else ""
        b, ht = g.ic
        manque = equi - taux_pct
        sous_h = (" — sous le hasard d&#39;une pièce lancée : le problème est "
                  "la construction des signaux, pas leur tri"
                  if f.sous_le_hasard else "")
        ligne_m = (f'<div class="manque">▼ il manque {manque:.0f} points · '
                   f'IC [{b:.0%} – {ht:.0%}] sur {g.n_resolus} résolus{sous_h}</div>'
                   if manque > 0 else
                   f'<div class="manque" style="color:var(--gain)">▲ '
                   f'{-manque:.0f} points au-dessus de l&#39;équilibre · '
                   f'IC [{b:.0%} – {ht:.0%}]</div>')
        jauge = (f'<div class="jauge"><div class="piste">'
                 f'<div class="rempli{ok}" style="width:{rempli:.0f}%"></div>'
                 f'<span class="dansbarre mono">{taux_pct:.0f} %</span>'
                 f'<div class="seuil" style="left:{seuil:.0f}%" '
                 f'data-l="équilibre {equi:.0f} %"></div></div></div>{ligne_m}')
    else:
        jauge = (f'<div class="gros" style="font-size:16px;margin-top:8px">'
                 f'{g.texte_taux}</div>'
                 '<div class="sous">un pourcentage sur si peu de trades serait '
                 'un tirage à pile ou face affiché en gras</div>')
    h.append(f'<div class="tuile"><div class="lab">Taux de validés contre '
             f'l&#39;équilibre</div>{jauge}</div>')

    # 3. Pips nets — signés, jamais une valeur absolue.
    cls_p = "neg" if g.pips_net < 0 else ("pos" if g.pips_net > 0 else "")
    p_txt = (f"{'−' if g.pips_net < 0 else '+' if g.pips_net > 0 else ''}"
             f"{abs(g.pips_net):,.0f}").replace(",", " ")
    h.append(f'<div class="tuile"><div class="lab">Pips nets ({f.unite})</div>'
             f'<div class="gros {cls_p} mono">{p_txt}</div>'
             f'<div class="sous">sur cet instrument seulement — un total '
             f'multi-marchés n&#39;est pas une somme d&#39;argent</div></div>')

    # 4. Résolus / émis
    emis = g.n_resolus + g.n_attente + g.n_expire
    h.append(f'<div class="tuile"><div class="lab">Résolus / émis</div>'
             f'<div class="gros mono">{g.n_resolus} / {emis}</div>'
             f'<div class="sous">{g.n_attente} en attente · {g.n_expire} '
             f'jamais entré(s), exclus du taux</div></div>')
    h.append('</div>')

    # ---- les 6 timeframes, pleine largeur (8.3) --------------------------
    h.append('<div class="tfs" id="tfs-fiche">')
    for tf, c in [("TOUS", g)] + list(f.timeframes.items()):
        verdict = c.verdict if tf != "TOUS" else ""
        v_cls = VERDICT_CLS.get(verdict, "insuf")
        attenue = " coupe" if verdict == "COUPÉ" else ""
        bip = (f'<span class="pastille">{f.tf_avec_signal.count(tf) or 1}</span>'
               if tf in f.tf_avec_signal else "")
        v_html = (f'<div class="v {v_cls}">{verdict.lower()}</div>' if verdict
                  else '<div class="v insuf">tous timeframes</div>')
        h.append(f'<button class="tfx{attenue}" data-tf="{tf}">'
                 f'<div class="n">{tf}</div>{v_html}'
                 f'<div class="e mono">n={c.n_resolus}</div>{bip}</button>')
    h.append('</div>')
    h.append(_bloc_chartiste(f.instrument))
    return "".join(h)


def _bloc_chartiste(instrument: str) -> str:
    """Étape 6ter : les NIVEAUX d'AG-20 sur la fiche (descriptifs), et les
    CONFLITS entre échelles — c'est eux qu'on regarde en premier."""
    try:
        from .chartiste import derniere
        L = derniere(instrument)
    except Exception:
        L = None
    if L is None or not L.par_tf:
        return ""
    morceaux = []
    for n in L.niveaux_fusionnes[:3]:
        morceaux.append(f'<b>{n["genre"]}</b> {n["prix"]:.5g} '
                        f'({n["touches"]} touches · {", ".join(n["timeframes"])})')
    niveaux_txt = " · ".join(morceaux) if morceaux else "aucun niveau majeur"
    h = [f'<div style="font-size:12px;color:var(--encre-2);margin:-6px 0 14px">'
         f'📐 AG-20 — {L.sens_dominant} sur {L.accord:.0%} des échelles · '
         f'{niveaux_txt}']
    for cfl in L.conflits[:2]:
        h.append(f'<div style="color:var(--attention);font-weight:600;'
                 f'margin-top:3px">⚠ {cfl}</div>')
    if L.n_uniques:
        h.append(f'<div style="color:var(--encre-3);margin-top:2px">'
                 f'{L.n_uniques} figure(s) distincte(s) '
                 f'({L.n_figures} détections brutes) — le bruit en donnerait '
                 f'{L.attendu_sur_bruit:.1f}</div>')
    h.append('</div>')
    return "".join(h)


def _ligne(s, unite: str) -> str:
    icone = {"TP": '<span class="res tp">✓ validé (TP)</span>',
             "SL": '<span class="res sl">✗ non validé (SL)</span>',
             "en_attente": '<span class="res at">◷ en attente</span>',
             "expire": '<span class="res at">— jamais entré</span>'} \
        .get(s.statut, s.statut)
    quand = (dt.datetime.fromtimestamp(s.cree_ts, dt.timezone.utc)
             .strftime("%d/%m %H:%M") if s.cree_ts else "—")
    try:
        import pips as _p
        p_val = _p.pips_signal(s)
    except Exception:
        p_val = None
    note = f"{round(s.note * 100)} %" if s.note is not None else "—"
    cause = ""
    if s.statut == "SL":
        if s.tp_atteint_apres_sl:
            cause = "stop trop serré"
        elif s.extreme_favorable is not None and s.risque:
            cause = ("direction fausse"
                     if abs(s.extreme_favorable - s.entree) / s.risque < 0.25
                     else "—")
        else:
            cause = "—"
    return (f'<tr data-tf="{s.tf}" data-etat="{s.statut}">'
            f'<td>{quand}</td><td><b>{s.tf}</b></td><td>{s.sens}</td>'
            f'<td class="num mono">{s.entree}</td>'
            f'<td class="num mono">{s.sl}</td><td class="num mono">{s.tp}</td>'
            f'<td class="num mono">{note}</td><td>{icone}</td>'
            f'<td class="num">{_signe(s.r_realise, 2)}</td>'
            f'<td class="num">{_signe(round(p_val) if p_val is not None else None)}</td>'
            f'<td class="cause">{cause or "—"}</td></tr>')


ENTETE_TABLE = ('<thead><tr><th>Émis (UTC)</th><th>TF</th><th>Sens</th>'
                '<th class="num">Entrée</th><th class="num">SL</th>'
                '<th class="num">TP</th><th class="num">Note</th>'
                '<th>Résultat</th><th class="num">R</th>'
                '<th class="num">Pips</th><th>Cause SL</th></tr></thead>')


def _puces_tf() -> str:
    return ('<button class="puce" data-ftf="TOUS" aria-pressed="true">Tous TF'
            '</button>' + "".join(f'<button class="puce" data-ftf="{tf}">{tf}'
                                  '</button>'
                                  for tf in ("H4", "H1", "M30", "M15", "M5")))


def bloc_bas(cle: str, _deja=None) -> str:
    """Onglets Signaux validés | Historique complet | Risque (maquette)."""
    inst, f = _deja or _fiche(cle)
    g = f.global_
    resolus = [s for s in f.signaux if s.statut in ("TP", "SL")]
    lignes_r = "".join(_ligne(s, f.unite) for s in resolus[:120])
    lignes_t = "".join(_ligne(s, f.unite) for s in f.signaux[:150])
    vide = ('<tr><td colspan="11" style="color:var(--encre-3)">aucun signal '
            'journalisé sur cet instrument</td></tr>')

    return f"""
<div class="onglets" id="onglets-fiche" role="tablist">
  <button class="onglet actif" data-pf="pf1" role="tab">Signaux validés<span class="cpt mono">{len(resolus)}</span></button>
  <button class="onglet" data-pf="pf2" role="tab">Historique complet<span class="cpt mono">{len(f.signaux)}</span></button>
  <button class="onglet" data-pf="pf3" role="tab">Risque événementiel</button>
</div>
<div class="panneau actif" id="pf1">
  <div class="filtres">{_puces_tf()}
    <span class="info">{f.instrument} seulement · 5 lignes visibles, fais défiler pour le reste</span></div>
  <div class="defile"><table>{ENTETE_TABLE}<tbody>{lignes_r or vide}</tbody></table></div>
  <div class="pied">{len(resolus)} résolus affichés · les signaux jamais entrés sont exclus
  du taux (règle 2) et listés dans l&#39;historique complet</div>
</div>
<div class="panneau" id="pf2">
  <div class="filtres">
    <button class="puce" data-fet="TOUS" aria-pressed="true">Tout</button>
    <button class="puce" data-fet="resolu">Résolus</button>
    <button class="puce" data-fet="en_attente">En attente</button>
    <button class="puce" data-fet="expire">Jamais entrés</button>
    <span class="info">tous les signaux de {f.instrument}, y compris les expirés</span></div>
  <div class="defile"><table>{ENTETE_TABLE}<tbody>{lignes_t or vide}</tbody></table></div>
  <div class="pied">{len(f.signaux)} signaux · {g.n_resolus} résolus ·
  {g.n_attente} en attente · {g.n_expire} jamais entrés</div>
</div>
<div class="panneau" id="pf3"><div id="hote-risque"></div></div>"""
