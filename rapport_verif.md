Le verificateur du projet signale les points suivants.
Corrige-les un par un, puis relance `python3 verif.py` et
montre-moi la sortie. N'annonce pas que c'est fini tant que
la sortie n'est pas verte.

## AVERTISSEMENTS (non bloquants, a traiter ensuite)
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