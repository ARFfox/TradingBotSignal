"""La fiche instrument du site (APPLIQUER étape 8, revue du 16/09 soir).

TOUS les calculs vivent dans `vue_instrument.py` (module livré, 29 tests) :
ce fichier ne fait que l'adaptation (journal → Signal, actifs normalisés)
et le rendu HTML. « Deux pages qui calculent le même taux finissent
toujours par afficher deux chiffres différents » — donc une seule source.
"""
from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

COULEUR_VERDICT = {"AUTORISÉ": "#3fb950", "COUPÉ": "#f85149",
                   "OBSERVATION": "#d29922", "INSUFFISANT": "#6e7681"}
ICONES = {"TP": ("✅ validé (TP)", "#3fb950"),
          "SL": ("❌ non validé (SL)", "#f85149"),
          "en_attente": ("🕐 en attente", "#8b949e"),
          "expire": ("⚪ jamais entré", "#6e7681")}


def _actifs() -> list[dict]:
    """Les signaux EN COURS, normalisés sur le SYMBOLE (le journal parle en
    symboles, les pastilles du site en clés — la traduction vit ici)."""
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
        try:                                # avant la première collecte
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
    f.marche = inst.marche                  # le registre fait foi
    return inst, f


def json_fiche(cle: str) -> dict:
    """La route /api/instrument/<cle> — le contrat exact d'APPLIQUER §8.2."""
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
            "cree_le": getattr(s, "cree_ts", 0), "tf": s.tf, "sens": s.sens,
            "entree": s.entree, "sl": s.sl, "tp": s.tp, "statut": s.statut,
            "r": s.r_realise} for s in f.signaux[:200]],
    }


def _bouton_tf(tf: str, c, en_signal: bool) -> str:
    coul = COULEUR_VERDICT.get(c.verdict, "#6e7681")
    gris = "opacity:.45;" if c.verdict == "COUPÉ" else ""
    bip = ('<span style="position:absolute;top:-7px;right:-7px;min-width:20px;'
           'height:20px;border-radius:99px;background:#f85149;color:#fff;'
           'font-size:11px;font-weight:800;line-height:20px;text-align:center;'
           'padding:0 4px">🔴</span>' if en_signal else "")
    return (f'<button class="tfb-fiche" data-tf="{tf}" onclick="'
            "var t=this.closest('#fiche-instrument');"
            "t.querySelectorAll('.tfb-fiche').forEach(b=>b.style.outline='');"
            "this.style.outline='2px solid #1f6feb';"
            "var f=this.dataset.tf;"
            "t.querySelectorAll('tr[data-tf]').forEach(r=>"
            "r.style.display=(f==='TOUS'||r.dataset.tf===f)?'':'none');\" "
            f'style="{gris}position:relative;background:#21262d;color:#c9d1d9;'
            'border:1px solid #30363d;border-radius:10px;padding:7px 12px;'
            'cursor:pointer;overflow:visible;text-align:center">'
            f'<div style="font-weight:800">{tf}</div>'
            f'<div style="font-size:10px;color:{coul};font-weight:700">'
            f'{c.verdict}</div>'
            f'<div style="font-size:9.5px;color:#6e7681">n={c.n_resolus}</div>'
            f'{bip}</button>')


def bloc_html(cle: str) -> str:
    """Le bloc fiche : titre + taux honnête + 5 TF + historique filtré.
    Tout chiffre affiché sort de vue_instrument, texte compris."""
    inst, f = _fiche(cle)
    g = f.global_
    h = ['<div class="strats" id="fiche-instrument" style="margin-bottom:12px">']
    sig_txt = (f' <span style="color:#f85149;font-weight:700">🔴 signal sur '
               f'{", ".join(f.tf_avec_signal)}</span>' if f.tf_avec_signal else "")
    h.append(f'<div style="font-size:15px;font-weight:800">{f.instrument} · '
             f'{inst.nom}{sig_txt}</div>')
    h.append(f'<div style="margin:6px 0;font-size:13px"><b>{g.texte_taux}</b></div>')
    pips_c = "#f85149" if g.pips_net < 0 else "#3fb950"
    h.append(f'<div style="font-size:12px;color:#8b949e">R cumulé '
             f'<b style="color:#e6edf3">{g.r_total:+.1f}R</b> · '
             f'<b style="color:{pips_c}">{g.pips_net:+,.0f}</b> {f.unite} · '
             f'{g.n_attente} en attente · {g.n_expire} jamais entrés '
             '<span style="color:#6e7681">(exclus du taux — règle 2)</span>'
             '</div>'.replace(",", " "))
    if f.sous_le_hasard:
        h.append(f'<div class="al chaud" style="margin-top:6px">⚠️ '
                 f'{g.taux:.0%} contre {g.hasard:.0%} pour une pièce lancée à '
                 'ce R:R — le problème n&#39;est pas le tri des signaux, '
                 'c&#39;est leur construction.</div>')

    # 8.3 : les 5 timeframes TOUJOURS affichés — absent = pas de données,
    # pas « pas de signal ». COUPÉ grisé mais cliquable.
    import dataclasses as _dc
    from vue_instrument import Case as _Case
    tous = _dc.replace(_Case("TOUS"), n_resolus=g.n_resolus)
    h.append('<div style="display:flex;gap:10px;margin:10px 0;overflow:visible">')
    h.append(_bouton_tf("TOUS", tous, False))
    for tf, c in f.timeframes.items():
        h.append(_bouton_tf(tf, c, tf in f.tf_avec_signal))
    h.append('</div>')

    import datetime as _dt
    lignes = []
    for s in f.signaux[:60]:
        icone, coul = ICONES.get(s.statut, (s.statut, "#8b949e"))
        quand = _dt.datetime.fromtimestamp(s.cree_ts, _dt.timezone.utc) \
            .strftime("%d/%m %H:%M") if s.cree_ts else "—"
        r_txt = f"{s.r_realise:+.2f}" if s.r_realise is not None else "—"
        estompe = ' style="opacity:.55"' if s.statut not in ("TP", "SL") else ""
        lignes.append(
            f'<tr data-tf="{s.tf}"{estompe}><td>{quand}</td><td>{s.tf}</td>'
            f'<td>{s.sens}</td><td>{s.entree}</td><td>{s.sl}</td><td>{s.tp}</td>'
            f'<td style="color:{coul}">{icone}</td><td>{r_txt}</td></tr>')
    if lignes:
        h.append('<table style="margin-top:4px"><tr><th>Émis (UTC)</th><th>TF</th>'
                 '<th>Sens</th><th>Entrée</th><th>SL</th><th>TP</th>'
                 '<th>Résultat</th><th>R</th></tr>' + "".join(lignes) + '</table>')
    else:
        h.append('<div style="font-size:12px;color:#6e7681;margin-top:6px">'
                 'aucun signal journalisé sur cet instrument</div>')
    h.append('</div>')
    return "".join(h)
