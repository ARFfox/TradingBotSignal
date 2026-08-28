#!/bin/bash
# Lanceur du tableau de bord — double-clique ce fichier depuis le Finder.
cd "$(dirname "$0")"

# Un serveur deja en route occuperait le port : on le remplace proprement.
if lsof -nP -iTCP:8787 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Un tableau de bord tourne deja sur le port 8787."
  echo "Ouvre http://127.0.0.1:8787 — ou ferme-le d'abord (Ctrl+C dans sa fenetre)."
  echo
  read -n 1 -s -r -p "Appuie sur une touche pour fermer."
  exit 0
fi

echo "Demarrage du tableau de bord..."
echo "Laisse CETTE FENETRE OUVERTE tant que tu veux les notifications."
echo "Ctrl+C pour arreter."
echo
python3 -u -m gold_agent.web
