# Blog des Wizards

Projet fil rouge du module FastAPI (EPSI).

## Prérequis

- Docker (Docker Desktop ou OrbStack) et Git
- [uv](https://docs.astral.sh/uv/) sur le poste, uniquement pour que l'éditeur trouve les paquets

## Démarrer

```bash
cp .env.example .env
docker compose up -d
docker compose ps
uv sync            # crée .venv sur le poste pour VS Code
```

Puis ouvrir <http://localhost:8000/docs>.

Toute commande Python ou uv s'exécute dans le conteneur :

```bash
docker compose exec app uv run python --version
```

## Valider un TP

Chaque TP a sa suite de tests dans `tests/validation/` (à ne pas modifier) :

```bash
docker compose exec app uv run pytest tests/validation/test_tp01.py
```

Tout est vert : le TP est terminé. Sinon, chaque échec explique ce qui manque.

`down -v` efface la base : à faire seulement quand on change de branche.
