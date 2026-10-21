"""TP 6 : afficher les articles, en JSON et en HTML.

docker compose exec app uv run python -m scripts.seed
docker compose exec app uv run pytest tests/validation/test_tp06.py
"""

import html
import re
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from tests.conftest import exiger, importer


def route_declaree(response, route):
    """Échoue si la route n'existe pas : le 404 par défaut de Starlette dit « Not Found »."""
    absente = response.status_code == 405 or (
        response.status_code == 404 and response.text == '{"detail":"Not Found"}'
    )
    if absente:
        pytest.fail(
            f"{route} répond {response.status_code} : la route est-elle déclarée ?",
            pytrace=False,
        )


@pytest.fixture
def articles(db):
    """Trois articles en base de test, créés à des dates différentes."""
    Article = importer("app.models.article", attendu_au="TP 5").Article
    maintenant = datetime(2026, 10, 1, 12, 0)
    crees = [
        Article(
            titre="Le plus ancien",
            contenu="Écrit il y a deux jours.",
            created_at=maintenant - timedelta(days=2),
        ),
        Article(
            titre="Le plus récent", contenu="Écrit aujourd'hui.", created_at=maintenant
        ),
        Article(
            titre="Celui du milieu",
            contenu="Écrit hier.",
            created_at=maintenant - timedelta(days=1),
        ),
    ]
    db.add_all(crees)
    db.commit()
    return {a.titre: a.id for a in crees}


def operation(client, methode, motif):
    for chemin, operations in client.get("/openapi.json").json()["paths"].items():
        if re.fullmatch(motif, chemin) and methode in operations:
            return operations[methode]
    pytest.fail(
        f"Aucune route {methode.upper()} {motif} dans /docs : est-elle déclarée ?",
        pytrace=False,
    )


# Le seed


def test_seed_cree_des_articles():
    exiger("faker", "sqlalchemy")
    resultat = subprocess.run(
        [sys.executable, "-m", "scripts.seed"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resultat.returncode == 0, (
        f"python -m scripts.seed a échoué :\n{resultat.stderr[-800:]}\n"
        "Le fichier scripts/seed.py existe-t-il, avec scripts/__init__.py ?"
    )
    from sqlalchemy import func, select

    db = importer("app.db", attendu_au="TP 5")
    Article = importer("app.models.article", attendu_au="TP 5").Article
    with db.SessionLocal() as session:
        nombre = session.scalar(select(func.count()).select_from(Article))
    assert nombre >= 10, (
        f"Après le seed, Postgres contient {nombre} articles : 10 attendus."
    )


# L'API JSON


def test_router_articles(client):
    for methode, motif in (
        ("get", r"/api/articles"),
        ("get", r"/api/articles/\{[^}]+\}"),
    ):
        tags = operation(client, methode, motif).get("tags", [])
        assert "articles" in tags, (
            f"{motif} doit être sous le tag « articles » : "
            'APIRouter(prefix="/api/articles", tags=["articles"]) dans app/routers/articles.py.'
        )


def test_liste_vide_sans_articles(client):
    response = client.get("/api/articles")
    route_declaree(response, "GET /api/articles")
    assert response.status_code == 200
    assert response.json() == [], (
        "Base vide, GET /api/articles doit renvoyer [] : les articles écrits en dur du TP 3 "
        "doivent disparaître, la liste vient de la base."
    )


def test_liste_du_plus_recent_au_plus_ancien(client, articles):
    response = client.get("/api/articles")
    assert response.status_code == 200, "GET /api/articles doit répondre 200."
    titres = [a["titre"] for a in response.json()]
    assert titres == ["Le plus récent", "Celui du milieu", "Le plus ancien"], (
        f"Ordre reçu : {titres}. Triez du plus récent au plus ancien : "
        "order_by(Article.created_at.desc())."
    )


def test_article_public_complet(client, articles):
    article = client.get("/api/articles").json()[0]
    for champ in ("id", "titre", "contenu", "created_at"):
        assert champ in article, (
            f"ArticlePublic doit renvoyer {champ} : ajoutez created_at au schéma, "
            "avec model_config = ConfigDict(from_attributes=True)."
        )


def test_liste_typee(client):
    reponse = operation(client, "get", r"/api/articles")["responses"]["200"]
    items = reponse["content"]["application/json"]["schema"].get("items", {})
    assert items.get("$ref", "").endswith("/ArticlePublic"), (
        "GET /api/articles doit être typée list[ArticlePublic] (response_model=list[ArticlePublic])."
    )


def test_detail(client, articles):
    identifiant = articles["Celui du milieu"]
    response = client.get(f"/api/articles/{identifiant}")
    route_declaree(response, f"GET /api/articles/{identifiant}")
    assert response.status_code == 200, (
        f"GET /api/articles/{identifiant} doit répondre 200."
    )
    assert response.json()["titre"] == "Celui du milieu"


def test_detail_introuvable(client, articles):
    response = client.get("/api/articles/999")
    route_declaree(response, "GET /api/articles/{article_id}")
    assert response.status_code == 404, (
        "GET /api/articles/999 doit répondre 404 : HTTPException(404, ...)."
    )


def test_404_documente(client):
    reponses = operation(client, "get", r"/api/articles/\{[^}]+\}")["responses"]
    assert "404" in reponses, (
        'Le 404 doit apparaître dans /docs : responses={404: {"description": "Article introuvable"}}.'
    )


# Les pages HTML


def test_page_liste(client, articles):
    response = client.get("/articles")
    route_declaree(response, "GET /articles")
    assert response.status_code == 200, "GET /articles doit répondre 200."
    assert response.headers["content-type"].startswith("text/html"), (
        "GET /articles doit renvoyer du HTML."
    )
    for titre, identifiant in articles.items():
        assert titre in response.text, f"La page /articles doit afficher « {titre} »."
        assert re.search(rf'href="[^"]*/articles/{identifiant}"', response.text), (
            f"La page /articles doit contenir un lien vers /articles/{identifiant} : "
            "url_for('show_article', article_id=article.id)."
        )


def test_page_detail(client, articles):
    identifiant = articles["Le plus récent"]
    response = client.get(f"/articles/{identifiant}")
    route_declaree(response, f"GET /articles/{identifiant}")
    assert response.status_code == 200, (
        f"GET /articles/{identifiant} doit répondre 200."
    )
    page = html.unescape(response.text)  # Jinja échappe l'apostrophe en &#39;
    assert "Le plus récent" in page and "Écrit aujourd'hui." in page, (
        "La page d'un article doit afficher son titre et son contenu."
    )


def test_page_detail_introuvable(client, articles):
    response = client.get("/articles/999")
    route_declaree(response, "GET /articles/{article_id}")
    assert response.status_code == 404, "GET /articles/999 doit répondre 404."


def test_route_nommee_show_article():
    from starlette.routing import NoMatchFound

    from app.main import app

    try:
        chemin = app.url_path_for("show_article", article_id=3)
    except NoMatchFound:
        pytest.fail(
            "Aucune route ne s'appelle show_article : "
            '@router.get("/articles/{article_id}", name="show_article").',
            pytrace=False,
        )
    assert chemin == "/articles/3", (
        f"url_for('show_article', article_id=3) donne {chemin}."
    )


def test_health_toujours_la(client):
    route_declaree(client.get("/health"), "GET /health (TP 2)")
