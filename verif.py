#!/usr/bin/env python3
"""
AG-99 VERIFICATEUR — le controle automatique du projet.

    python3 verif.py              # controle complet
    python3 verif.py --rapide     # sans les tests lents
    python3 verif.py --prompt     # n'affiche que le prompt pour Claude Code

Ce que le verificateur fait, tout seul :
  1. verifie que chaque fichier Python compile
  2. importe chaque module et attrape les erreurs d'import
  3. distingue une DEPENDANCE MANQUANTE d'une ERREUR DE CODE (ce n'est pas
     le meme probleme et ca n'appelle pas la meme correction)
  4. lance les tests unitaires de tests/
  5. controle les invariants du projet (constantes en dur, symboles cables,
     fichiers trop longs, cles API dans le code)
  6. fait tourner a blanc les modules de calcul sur donnees synthetiques
  7. ecrit rapport_verif.md avec un PROMPT PRET A COLLER dans Claude Code

Code de sortie : 0 si tout passe, 1 sinon. Claude Code doit relancer ce
script apres chaque modification et n'a pas le droit d'annoncer qu'une
tache est finie tant que la sortie n'est pas verte.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import io
import contextlib
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv",
               "site-packages", ".idea", "build", "dist"}

# Modules externes attendus : leur absence est un probleme d'INSTALLATION,
# jamais une erreur de code. Le verificateur ne doit pas les confondre.
DEPENDANCES = {"yfinance", "pandas", "numpy", "requests", "duckdb",
               "fastapi", "aiohttp", "websockets", "matplotlib", "pytest",
               "scipy", "sklearn"}

LIGNES_MAX = 500


# --------------------------------------------------------------------------
@dataclass
class Souci:
    gravite: str          # "ERREUR" | "AVERTISSEMENT" | "INFO"
    controle: str
    fichier: str
    detail: str
    ligne: int | None = None
    piste: str = ""

    def __str__(self) -> str:
        loc = f"{self.fichier}:{self.ligne}" if self.ligne else self.fichier
        s = f"[{self.gravite}] {self.controle} — {loc}\n    {self.detail}"
        return s + (f"\n    piste : {self.piste}" if self.piste else "")


@dataclass
class Rapport:
    soucis: list[Souci] = field(default_factory=list)
    manquantes: set[str] = field(default_factory=set)
    ok: list[str] = field(default_factory=list)

    def erreurs(self) -> list[Souci]:
        return [s for s in self.soucis if s.gravite == "ERREUR"]

    def avertissements(self) -> list[Souci]:
        return [s for s in self.soucis if s.gravite == "AVERTISSEMENT"]

    def vert(self) -> bool:
        return not self.erreurs()


# --------------------------------------------------------------------------
def fichiers_python() -> list[Path]:
    out = []
    for p in RACINE.rglob("*.py"):
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def nom_de_module(f: Path) -> str | None:
    """Nom pointe si le fichier appartient a un paquet, sinon None.

    Un module de paquet (gold_agent/analyze.py) fait `from . import x` : le
    charger isolement leve toujours "attempted relative import with no known
    parent package". Ce n'est PAS une erreur du code, c'est une erreur de
    methode du verificateur. Il faut l'importer par son chemin pointe,
    gold_agent.analyze, avec la racine sur sys.path.
    """
    parts = []
    d = f.parent
    while d != RACINE and (d / "__init__.py").exists():
        parts.insert(0, d.name)
        d = d.parent
    if not parts or d != RACINE:
        return None
    return ".".join(parts + [f.stem])


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(RACINE))
    except ValueError:
        return str(p)


# --- 1. syntaxe -----------------------------------------------------------
def controle_syntaxe(r: Rapport, fichiers: list[Path]) -> None:
    for f in fichiers:
        try:
            ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as e:
            r.soucis.append(Souci("ERREUR", "syntaxe", rel(f),
                                  f"{e.msg}", e.lineno,
                                  "erreur de syntaxe : le fichier ne compile pas"))
        except Exception as e:
            r.soucis.append(Souci("ERREUR", "syntaxe", rel(f), str(e)))
    if not any(s.controle == "syntaxe" for s in r.soucis):
        r.ok.append(f"syntaxe : {len(fichiers)} fichiers compilent")


# --- 2. imports -----------------------------------------------------------
def _nom_module_manquant(tb: str) -> str | None:
    for ligne in tb.splitlines():
        if "ModuleNotFoundError" in ligne and "'" in ligne:
            return ligne.split("'")[1].split(".")[0]
    return None


def controle_imports(r: Rapport, fichiers: list[Path]) -> None:
    testes = 0
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    for f in fichiers:
        if f.name == Path(__file__).name or f.name.startswith("test_"):
            continue
        # Un module de paquet s'importe par son chemin pointe, pas isolement.
        pointe = nom_de_module(f)
        if pointe:
            if f.stem == "__init__":
                continue
            try:
                with contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(io.StringIO()):
                    importlib.import_module(pointe)
                testes += 1
            except ModuleNotFoundError as e:
                m = (e.name or "").split(".")[0]
                if m in DEPENDANCES:
                    r.manquantes.add(m)
                else:
                    r.soucis.append(Souci("ERREUR", "import", rel(f),
                                          f"module introuvable : {m}",
                                          piste="dependance non declaree, ou faute de frappe"))
            except Exception:
                tb = traceback.format_exc()
                m = _nom_module_manquant(tb)
                if m in DEPENDANCES:
                    r.manquantes.add(m)
                else:
                    r.soucis.append(Souci("ERREUR", "import", rel(f),
                                          tb.strip().splitlines()[-1], None,
                                          "le module leve une exception au chargement"))
            continue

        faux_nom = f"_v_{f.stem}"
        spec = importlib.util.spec_from_file_location(faux_nom, f)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            # Enregistrer AVANT d'executer : @dataclass, @enum et pickle
            # vont chercher sys.modules[cls.__module__] pendant l'execution
            # du corps du module. Sans cette ligne, tout fichier contenant
            # une dataclass echoue avec une AttributeError trompeuse.
            sys.modules[faux_nom] = mod
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                spec.loader.exec_module(mod)
            testes += 1
        except ModuleNotFoundError as e:
            manquant = (e.name or "").split(".")[0]
            if manquant in DEPENDANCES:
                r.manquantes.add(manquant)
            elif manquant.startswith(("gold_agent", "core", "feeds", "agents")):
                # import relatif d'un paquet : normal hors contexte
                testes += 1
            else:
                r.soucis.append(Souci("ERREUR", "import", rel(f),
                                      f"module introuvable : {manquant}",
                                      piste="dependance non declaree, ou faute de frappe"))
        except Exception:
            tb = traceback.format_exc()
            manquant = _nom_module_manquant(tb)
            if manquant in DEPENDANCES:
                r.manquantes.add(manquant)
                continue
            derniere = tb.strip().splitlines()[-1]
            ligne = None
            for l in reversed(tb.splitlines()):
                if str(f) in l and ", line " in l:
                    try:
                        ligne = int(l.split(", line ")[1].split(",")[0])
                    except Exception:
                        pass
                    break
            r.soucis.append(Souci("ERREUR", "import", rel(f), derniere, ligne,
                                  "le module leve une exception au chargement"))
        finally:
            sys.modules.pop(faux_nom, None)
    if testes:
        r.ok.append(f"imports : {testes} modules se chargent")


# --- 3. tests unitaires ---------------------------------------------------
def controle_tests(r: Rapport, rapide: bool) -> None:
    dossier = RACINE / "tests"
    if not dossier.exists():
        r.soucis.append(Souci("AVERTISSEMENT", "tests", "tests/",
                              "aucun dossier tests/",
                              piste="tout module de calcul doit avoir ses tests"))
        return
    if rapide:
        return
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", str(dossier), "-q",
                            "--no-header", "-x"],
                           capture_output=True, text=True, timeout=300, cwd=RACINE)
    except FileNotFoundError:
        r.soucis.append(Souci("AVERTISSEMENT", "tests", "tests/",
                              "pytest introuvable", piste="pip3 install pytest"))
        return
    except subprocess.TimeoutExpired:
        r.soucis.append(Souci("ERREUR", "tests", "tests/", "les tests depassent 5 min"))
        return

    sortie = (p.stdout + p.stderr).strip()
    if "No module named pytest" in sortie:
        r.manquantes.add("pytest")
        return
    if p.returncode == 0:
        derniere = sortie.splitlines()[-1] if sortie else "ok"
        r.ok.append(f"tests : {derniere}")
    else:
        extrait = "\n".join(sortie.splitlines()[-25:])
        r.soucis.append(Souci("ERREUR", "tests", "tests/",
                              "des tests echouent :\n" + extrait))


# --- 4. invariants du projet ---------------------------------------------
INVARIANTS = [
    ("VALEUR_POINT_PAR_LOT", "ERREUR",
     "valeur du point ecrite en dur — fausse partout sauf sur l'or",
     "doit venir de l'objet Instrument (regle 13 du CLAUDE.md)"),
    ('"XAU/USD"', "AVERTISSEMENT",
     "symbole cable en dur",
     "la fonction doit recevoir un Instrument en parametre"),
    ("'XAU/USD'", "AVERTISSEMENT",
     "symbole cable en dur",
     "la fonction doit recevoir un Instrument en parametre"),
]

# Ne doit se declencher que sur une VALEUR LITTERALE. `f"...&apikey={k}"`
# interpole une variable : c'est le bon usage, pas une fuite. Une regle
# qui les confond noie les vraies fuites sous des faux positifs, et on
# finit par ignorer le controle.
MOTIF_SECRET = re.compile(
    r"""(api[_-]?key|apikey|secret|token|password|passwd)\s*[=:]\s*['"][A-Za-z0-9_\-]{12,}['"]""",
    re.IGNORECASE)


def controle_invariants(r: Rapport, fichiers: list[Path]) -> None:
    for f in fichiers:
        if f.name == Path(__file__).name:
            continue
        try:
            lignes = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        if len(lignes) > LIGNES_MAX:
            r.soucis.append(Souci("AVERTISSEMENT", "taille", rel(f),
                                  f"{len(lignes)} lignes (max {LIGNES_MAX})",
                                  piste="a decouper (regle 16 du CLAUDE.md)"))

        for i, l in enumerate(lignes, 1):
            nu = l.strip()
            if nu.startswith("#"):
                continue
            for motif, gravite, detail, piste in INVARIANTS:
                if motif in l:
                    r.soucis.append(Souci(gravite, "invariant", rel(f),
                                          f"{detail} : {nu[:70]}", i, piste))
            if MOTIF_SECRET.search(l):
                r.soucis.append(Souci("ERREUR", "secret", rel(f),
                                      "cle API en dur dans le code", i,
                                      "utiliser .env (regle 12 du CLAUDE.md)"))


# --- 5. marche a blanc ----------------------------------------------------
def controle_calculs(r: Rapport) -> None:
    """Fait tourner les modules de calcul sur donnees synthetiques.

    Aucun reseau : c'est ce qui rend ce controle utilisable partout et
    reproductible. Un module de calcul qui a besoin d'internet pour etre
    teste est un module mal decoupe.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        r.manquantes.update({"numpy", "pandas"})
        return

    chemin = RACINE / "constellation_agent.py"
    if not chemin.exists():
        return
    try:
        spec = importlib.util.spec_from_file_location("_ca", chemin)
        ca = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(ca)
    except Exception:
        return  # deja signale par controle_imports

    try:
        rng = np.random.default_rng(0)
        idx = pd.date_range("2024-01-01", periods=700, freq="D")
        g = rng.normal(0, .01, len(idx))
        prix = pd.DataFrame({
            "PIVOT": 100 * np.exp(np.cumsum(g)),
            "SAT": 100 * np.exp(np.cumsum(1.4 * g + rng.normal(0, .006, len(idx)))),
            "MIR": 100 * np.exp(np.cumsum(-0.9 * g + rng.normal(0, .005, len(idx)))),
        }, index=idx)

        ag = ca.Constellation(prix, cache=None)
        membres = ag.membres("PIVOT")
        assert membres, "aucun membre calcule sur un jeu pourtant correle"
        gr = {m.ticker: m.groupe for m in membres}
        assert gr.get("SAT") == "satellite", f"SAT classe {gr.get('SAT')}"
        assert gr.get("MIR") == "miroir", f"MIR classe {gr.get('MIR')}"

        mi = ca.Miroir(ag)
        c1, s1 = mi.appliquer("PIVOT", "achat", 0.6,
                              {"SAT": "haussier", "MIR": "baissier"})
        c2, s2 = mi.appliquer("PIVOT", "achat", 0.6,
                              {"SAT": "baissier", "MIR": "haussier"})
        assert c1 > 0.6, f"confirmation totale n'augmente pas la confiance ({c1})"
        assert c2 < 0.6, f"contradiction totale n'abaisse pas la confiance ({c2})"
        assert -1.0 <= s1.score <= 1.0, "score hors bornes"
        r.ok.append("calculs : constellation + miroir coherents sur jeu synthetique")
    except AssertionError as e:
        r.soucis.append(Souci("ERREUR", "calcul", "constellation_agent.py",
                              f"invariant metier viole : {e}"))
    except Exception:
        r.soucis.append(Souci("ERREUR", "calcul", "constellation_agent.py",
                              traceback.format_exc().strip().splitlines()[-1]))


# --------------------------------------------------------------------------
def prompt_claude_code(r: Rapport) -> str:
    if r.vert() and not r.avertissements():
        return ""
    lignes = ["Le verificateur du projet signale les points suivants.",
              "Corrige-les un par un, puis relance `python3 verif.py` et",
              "montre-moi la sortie. N'annonce pas que c'est fini tant que",
              "la sortie n'est pas verte.", ""]
    if r.erreurs():
        lignes.append("## ERREURS (bloquantes)")
        for s in r.erreurs():
            loc = f"{s.fichier}:{s.ligne}" if s.ligne else s.fichier
            lignes.append(f"- **{loc}** — {s.detail}")
            if s.piste:
                lignes.append(f"  - piste : {s.piste}")
        lignes.append("")
    if r.avertissements():
        lignes.append("## AVERTISSEMENTS (non bloquants, a traiter ensuite)")
        for s in r.avertissements():
            loc = f"{s.fichier}:{s.ligne}" if s.ligne else s.fichier
            lignes.append(f"- **{loc}** — {s.detail}")
            if s.piste:
                lignes.append(f"  - piste : {s.piste}")
        lignes.append("")
    lignes += ["## Regles a respecter pendant la correction",
               "- ne corrige QUE ce qui est signale, rien d'autre",
               "- aucune correction ne doit changer le comportement sur XAU/USD",
               "- toute nouvelle fonction de calcul arrive avec son test dans tests/",
               "- relance `python3 verif.py` apres chaque fichier modifie"]
    return "\n".join(lignes)


def afficher(r: Rapport) -> None:
    L = "=" * 74
    print(f"\n{L}\n  VERIFICATEUR — {RACINE.name}\n{L}")

    for o in r.ok:
        print(f"  OK   {o}")

    if r.manquantes:
        print(f"\n  DEPENDANCES ABSENTES (installation, pas erreur de code) :")
        print(f"       pip3 install {' '.join(sorted(r.manquantes))}")

    err, avt = r.erreurs(), r.avertissements()
    if err:
        print(f"\n{L}\n  {len(err)} ERREUR(S)\n{L}")
        for s in err:
            print(f"\n{s}")
    if avt:
        print(f"\n{L}\n  {len(avt)} AVERTISSEMENT(S)\n{L}")
        for s in avt:
            print(f"\n{s}")

    print(f"\n{L}")
    if r.vert():
        print("  RESULTAT : VERT" + (f" ({len(avt)} avertissement(s))" if avt else ""))
    else:
        print(f"  RESULTAT : ROUGE — {len(err)} erreur(s) bloquante(s)")
    print(L)

    p = prompt_claude_code(r)
    if p:
        (RACINE / "rapport_verif.md").write_text(p, encoding="utf-8")
        print("\n  -> rapport_verif.md ecrit : colle-le dans Claude Code,")
        print("     ou dis-lui simplement : \"lance verif.py et corrige\".\n")


def main() -> int:
    rapide = "--rapide" in sys.argv
    seul_prompt = "--prompt" in sys.argv

    r = Rapport()
    fichiers = fichiers_python()
    controle_syntaxe(r, fichiers)
    controle_imports(r, fichiers)
    controle_invariants(r, fichiers)
    controle_calculs(r)
    controle_tests(r, rapide)

    if seul_prompt:
        print(prompt_claude_code(r) or "Rien a signaler.")
    else:
        afficher(r)
    return 0 if r.vert() else 1


if __name__ == "__main__":
    sys.exit(main())
