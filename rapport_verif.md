Le verificateur du projet signale les points suivants.
Corrige-les un par un, puis relance `python3 verif.py` et
montre-moi la sortie. N'annonce pas que c'est fini tant que
la sortie n'est pas verte.

## AVERTISSEMENTS (non bloquants, a traiter ensuite)
- **constellation_agent.py** — 510 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **gold_agent/backtest.py:51** — symbole cable en dur : sym = "XAU/USD"
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/datasource.py:166** — symbole cable en dur : def twelvedata_bars(symbole: str = "XAU/USD", tf: str = "60",
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/datasource.py:268** — symbole cable en dur : def quote_direct(symbole: str = "XAU/USD", ttl: int | None = None) -> 
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:15** — symbole cable en dur : symbole: str          # identifiant Twelve Data (ex : "XAU/USD")
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:22** — symbole cable en dur : "XAU/USD": Instrument("XAU/USD", "Or spot", 100.0, 2),
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/instruments.py:28** — symbole cable en dur : return REGISTRE["XAU/USD"]
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/news.py** — 556 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **gold_agent/news.py:250** — symbole cable en dur : oro = ds.twelvedata_bars("XAU/USD", "D", fenetre + 10)
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/news.py:520** — symbole cable en dur : bars = ds.twelvedata_bars("XAU/USD", "D", 5000)
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/tableau.py** — 1020 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **gold_agent/tableau.py:398** — symbole cable en dur : def collecter(symbole: str = "XAU/USD", bougies: int = 600) -> dict:
  - piste : la fonction doit recevoir un Instrument en parametre
- **gold_agent/web.py** — 1835 lignes (max 500)
  - piste : a decouper (regle 16 du CLAUDE.md)
- **tests/test_instruments.py:34** — symbole cable en dur : assert instruments.par_defaut().symbole == "XAU/USD"
  - piste : la fonction doit recevoir un Instrument en parametre

## Regles a respecter pendant la correction
- ne corrige QUE ce qui est signale, rien d'autre
- aucune correction ne doit changer le comportement sur XAU/USD
- toute nouvelle fonction de calcul arrive avec son test dans tests/
- relance `python3 verif.py` apres chaque fichier modifie