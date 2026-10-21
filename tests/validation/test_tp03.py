"""TP 3 : des schémas et une page.

docker compose exec app uv run pytest tests/validation/test_tp03.py
"""

from pathlib import Path

import pytest

TEMPLATES = Path("app/templates")


def route_declaree(response, route):
    """Échoue avec un message clair si la route n'existe pas encore."""
    if response.status_code in (404, 405):
        pytest.fail(
            f"{route} répond {response.status_code} : la route est-elle déclarée ?",
            pytrace=False,
        )


def test_schemas_importables():
    try:
        from app.schemas.article import ArticleBase, ArticleCreate, ArticlePublic
    except ImportError as exc:
        pytest.fail(
            f"app/schemas/article.py doit définir ArticleBase, ArticleCreate et "
            f"ArticlePublic ({exc}). Le dossier app/schemas/ a-t-il un __init__.py ?",
            pytrace=False,
        )
    assert issubclass(ArticleCreate, ArticleBase), (
        "ArticleCreate doit hériter d'ArticleBase."
    )
    assert issubclass(ArticlePublic, ArticleBase), (
        "ArticlePublic doit hériter d'ArticleBase."
    )
    assert "id" in ArticlePublic.model_fields, "ArticlePublic doit avoir un champ id."
    assert "id" not in ArticleCreate.model_fields, (
        "ArticleCreate ne doit pas avoir d'id : un client ne choisit pas son id."
    )


def test_liste_des_articles(client):
    response = client.get("/api/articles")
    route_declaree(response, "GET /api/articles")
    assert response.status_code == 200, "GET /api/articles doit répondre 200."
    articles = response.json()
    assert isinstance(articles, list), "GET /api/articles doit renvoyer une liste."
    assert len(articles) == 3, (
        f"3 articles écrits en dur attendus, {len(articles)} reçus."
    )
    for article in articles:
        for champ in ("id", "titre", "contenu"):
            assert champ in article, (
                f"Chaque article doit avoir un champ {champ} : {article}"
            )


def test_liste_typee_dans_la_documentation(client):
    operation = (
        client.get("/openapi.json").json()["paths"].get("/api/articles", {}).get("get")
    )
    if operation is None:
        pytest.fail(
            "GET /api/articles n'apparaît pas dans /docs : la route est-elle déclarée ?",
            pytrace=False,
        )
    reponse = operation["responses"]["200"]
    items = reponse["content"]["application/json"]["schema"].get("items", {})
    assert items.get("$ref", "").endswith("/ArticlePublic"), (
        "GET /api/articles doit être typée list[ArticlePublic] : "
        "ajoutez -> list[ArticlePublic] à la fonction."
    )


def test_creation(client):
    response = client.post(
        "/api/articles", json={"titre": "Mon article", "contenu": "Du contenu"}
    )
    route_declaree(response, "POST /api/articles")
    assert response.status_code == 201, (
        f"POST /api/articles doit répondre 201, pas {response.status_code} : "
        "status_code=201 dans le décorateur."
    )
    article = response.json()
    assert isinstance(article.get("id"), int), "L'article créé doit avoir un id entier."
    assert article["titre"] == "Mon article", (
        "L'article renvoyé doit reprendre le titre envoyé."
    )
    assert article["contenu"] == "Du contenu", (
        "L'article renvoyé doit reprendre le contenu envoyé."
    )


def test_le_client_ne_choisit_pas_son_id(client):
    response = client.post(
        "/api/articles",
        json={"id": 999, "titre": "Mon article", "contenu": "Du contenu"},
    )
    assert response.status_code == 201
    assert response.json()["id"] != 999, (
        "L'id envoyé par le client doit être ignoré : c'est le serveur qui le choisit."
    )


@pytest.mark.parametrize(
    "corps",
    [
        {"contenu": "Du contenu"},
        {"titre": "Mon article"},
        {"titre": 42, "contenu": "x"},
    ],
    ids=["sans titre", "sans contenu", "titre non texte"],
)
def test_creation_invalide(client, corps):
    response = client.post("/api/articles", json=corps)
    route_declaree(response, "POST /api/articles")
    assert response.status_code == 422, (
        f"POST /api/articles avec {corps} doit répondre 422 : "
        "le corps est-il typé avec ArticleCreate ?"
    )


@pytest.mark.parametrize("fichier", ["base.html", "home.html"])
def test_gabarits_presents(fichier):
    assert (TEMPLATES / fichier).is_file(), (
        f"Le gabarit app/templates/{fichier} est absent."
    )


def test_home_etend_base():
    home = TEMPLATES / "home.html"
    if not home.is_file():
        pytest.fail("Le gabarit app/templates/home.html est absent.", pytrace=False)
    contenu = home.read_text()
    assert "extends" in contenu and "base.html" in contenu, (
        'home.html doit commencer par {% extends "base.html" %}.'
    )


def test_page_d_accueil(client):
    response = client.get("/")
    route_declaree(response, "GET /")
    assert response.status_code == 200, "GET / doit répondre 200."
    assert response.headers["content-type"].startswith("text/html"), (
        "GET / doit maintenant renvoyer du HTML : remplacez la route JSON du TP 2 "
        "par une route en response_class=HTMLResponse."
    )
    page = response.text
    for article in client.get("/api/articles").json():
        assert article["titre"] in page, (
            f"La page d'accueil doit afficher « {article['titre']} »."
        )
    for balise in ("<header", "<footer"):
        assert balise in page, (
            f"La page d'accueil doit contenir le {balise}> de base.html : "
            "le header et le footer sont écrits une seule fois, dans le gabarit."
        )


def test_health_toujours_la(client):
    response = client.get("/health")
    route_declaree(response, "GET /health (TP 2)")
