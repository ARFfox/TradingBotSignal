Le verificateur du projet signale les points suivants.
Corrige-les un par un, puis relance `python3 verif.py` et
montre-moi la sortie. N'annonce pas que c'est fini tant que
la sortie n'est pas verte.

## AVERTISSEMENTS (non bloquants, a traiter ensuite)
- **avocats.py** — 544 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **bundle/avocats.py** — 544 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **bundle/constellation_agent.py** — 510 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **bundle/superviseur_apprenant.py** — 552 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **gold_agent/instruments.py:26** — symbole cable en dur : symbole: str          # identifiant canonique AFFICHÉ (ex : "XAU/USD")
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:67** — symbole cable en dur : _i("XAU/USD", "Or spot", "matieres", "OANDA:XAUUSD", "GC=F",
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:68** — symbole cable en dur : td="XAU/USD", point=100.0, dec=2, cout=0.007),
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:172** — symbole cable en dur : return REGISTRE["XAU/USD"]
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:193** — symbole cable en dur : ALIAS = {"XAUUSD": "XAU/USD", "GOLD": "XAU/USD"}
  - piste : la fonction doit recevoir un Instrument en parametre
- **superviseur_apprenant.py** — 552 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **tests/test_apprentissage.py:11** — symbole cable en dur : def _entree(statut="gagnant", instrument="XAU/USD", tf="H1", sens="ach
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_apprentissage.py:40** — symbole cable en dur : assert journal.resoudre({"H1": bars}, instrument="XAU/USD") >= 1
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_calibrage_applique.py:52** — symbole cable en dur : motif = apprentissage.refus_calibrage("XAU/USD", "M5", 80)
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_calibrage_applique.py:54** — symbole cable en dur : assert apprentissage.refus_calibrage("XAU/USD", "H1", 80) is None
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_calibrage_applique.py:65** — symbole cable en dur : assert apprentissage.refus_calibrage("XAU/USD", "M5", 5) is None
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_calibrage_applique.py:74** — symbole cable en dur : assert apprentissage.refus_calibrage("XAU/USD", "M5", 35)
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_calibrage_applique.py:75** — symbole cable en dur : assert apprentissage.refus_calibrage("XAU/USD", "M5", 55) is None
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_calibrage_applique.py:84** — symbole cable en dur : "cle": f"XAU/USD|M5|achat|{100 + i}", "instrument": "XAU/USD",
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_debat_pont.py:16** — symbole cable en dur : v = examiner_setup(st, instrument="XAU/USD", tf="M5", atr=2.0, spread=
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_debat_pont.py:25** — symbole cable en dur : v = examiner_setup(st, instrument="XAU/USD", tf="H1", atr=2.0, spread=
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_debat_pont.py:50** — symbole cable en dur : v = examiner_setup(st, instrument="XAU/USD", tf="H1", atr=2.0, spread=
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_instruments.py:34** — symbole cable en dur : assert instruments.par_defaut().symbole == "XAU/USD"
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_instruments.py:40** — symbole cable en dur : assert instruments.depuis_alias("OANDA:XAUUSD").symbole == "XAU/USD"
  - piste : la fonction doit recevoir un Instrument en parametre
- **tests/test_instruments.py:41** — symbole cable en dur : assert instruments.depuis_alias("gold").symbole == "XAU/USD"
  - piste : la fonction doit recevoir un Instrument en parametre

## Regles a respecter pendant la correction
- ne corrige QUE ce qui est signale, rien d'autre
- aucune correction ne doit changer le comportement sur XAU/USD
- toute nouvelle fonction de calcul arrive avec son test dans tests/
- relance `python3 verif.py` apres chaque fichier modifie