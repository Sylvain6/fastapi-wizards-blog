"""TP 1 : l'environnement tourne.

docker compose exec app uv run pytest tests/validation/test_tp01.py
"""

import os
import socket
import sys
import urllib.error
import urllib.request

import pytest


def test_python_313():
    version = sys.version.split()[0]
    assert sys.version_info[:2] == (3, 13), (
        f"Python 3.13 attendu, trouvé {version} : la commande doit être lancée "
        "dans le conteneur (docker compose exec app ...)"
    )


@pytest.mark.parametrize("variable", ["DATABASE_URL", "SECRET_KEY"])
def test_variables_d_environnement(variable):
    assert os.environ.get(variable), (
        f"{variable} est absente : avez-vous copié .env.example en .env, "
        "puis relancé docker compose up -d ?"
    )


def test_base_de_donnees_joignable():
    try:
        socket.create_connection(("database", 5432), timeout=3).close()
    except OSError as exc:
        pytest.fail(
            f"Le service database ne répond pas sur le port 5432 ({exc}) : "
            "docker compose ps doit afficher database en état healthy.",
            pytrace=False,
        )


def test_serveur_uvicorn_repond():
    try:
        urllib.request.urlopen("http://localhost:80/docs", timeout=3)
    except (urllib.error.URLError, OSError) as exc:
        pytest.fail(
            f"Le serveur ne répond pas dans le conteneur ({exc}) : "
            "docker compose logs app doit afficher « Uvicorn running on ».",
            pytrace=False,
        )


def test_documentation_disponible(client):
    response = client.get("/docs")
    assert response.status_code == 200, "La page /docs doit s'afficher."


def test_racine_sans_route(client):
    response = client.get("/")
    assert response.status_code == 404, (
        "Au TP 1, aucune route n'existe encore : / doit répondre 404."
    )
