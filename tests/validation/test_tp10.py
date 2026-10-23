"""TP 10 : recherche et commentaires.

docker compose exec app uv run alembic upgrade head
docker compose exec app uv run pytest tests/validation/test_tp10.py
"""

import json

import pytest

from tests.conftest import exiger, importer, route_declaree

CONTENU = "Un contenu assez long."


def creer_article(client, auteur, titre="Un article à commenter"):
    response = client.post(
        "/api/articles",
        json={"titre": titre, "contenu": CONTENU},
        headers=auteur["headers"],
    )
    assert response.status_code == 201, (
        f"Création d'article impossible : {response.text[:200]}"
    )
    return response.json()


def commenter(client, auteur, article_id, contenu="Bravo pour cet article !"):
    response = client.post(
        f"/api/articles/{article_id}/comments",
        json={"contenu": contenu},
        headers=auteur["headers"],
    )
    route_declaree(response, "POST /api/articles/{article_id}/comments")
    return response


# Le modèle


def test_modele_comment():
    Comment = importer("app.models.comment", attendu_au="TP 10").Comment
    colonnes = Comment.__table__.columns
    for nom in ("id", "contenu", "created_at", "article_id", "author_id"):
        assert nom in colonnes, f"Le modèle Comment doit avoir une colonne {nom}."
    cibles = {cle.column.table.name for cle in Comment.__table__.foreign_keys}
    Article = importer("app.models.article", attendu_au="TP 5").Article
    User = importer("app.models.user", attendu_au="TP 9").User
    assert Article.__tablename__ in cibles and User.__tablename__ in cibles, (
        "Comment doit être lié à Article (article_id) et à User (author_id) par des ForeignKey."
    )


# Les commentaires dans l'API


def test_commenter_exige_d_etre_connecte(client, alice):
    article = creer_article(client, alice)
    response = client.post(
        f"/api/articles/{article['id']}/comments", json={"contenu": "Bravo !"}
    )
    route_declaree(response, "POST /api/articles/{article_id}/comments")
    assert response.status_code == 401, (
        "Commenter sans jeton doit répondre 401 : CurrentUser."
    )


def test_commenter(client, alice, bob):
    article = creer_article(client, alice)
    response = commenter(client, bob, article["id"])
    assert response.status_code == 201, (
        f"Commenter doit répondre 201, pas {response.status_code}."
    )
    commentaire = response.json()
    assert commentaire.get("contenu") == "Bravo pour cet article !"
    assert "bob@blog.fr" in json.dumps(commentaire), (
        "Le commentaire renvoyé doit indiquer son auteur (son email), "
        "par exemple un champ author imbriqué."
    )


def test_commenter_un_article_inexistant(client, alice):
    response = commenter(client, alice, 999)
    assert response.status_code == 404, (
        "Commenter un article inexistant doit répondre 404."
    )


def test_liste_des_commentaires(client, alice, bob):
    article = creer_article(client, alice)
    autre = creer_article(client, alice, "Un autre article")
    commenter(client, bob, article["id"], "Premier commentaire")
    commenter(client, alice, article["id"], "Second commentaire")
    commenter(client, bob, autre["id"], "Sur un autre article")
    response = client.get(f"/api/articles/{article['id']}/comments")
    route_declaree(response, "GET /api/articles/{article_id}/comments")
    assert response.status_code == 200, "La liste des commentaires est publique (200)."
    commentaires = response.json()
    assert sorted(c["contenu"] for c in commentaires) == [
        "Premier commentaire",
        "Second commentaire",
    ], "GET doit renvoyer les commentaires de cet article, et seulement eux."
    for commentaire in commentaires:
        auteur = (
            "bob@blog.fr"
            if commentaire["contenu"] == "Premier commentaire"
            else "alice@blog.fr"
        )
        assert auteur in json.dumps(commentaire), (
            "Chaque commentaire doit indiquer son auteur."
        )


def test_commentaires_d_un_article_inexistant(client):
    response = client.get("/api/articles/999/comments")
    route_declaree(response, "GET /api/articles/{article_id}/comments")
    assert response.status_code == 404, (
        "Les commentaires d'un article inexistant : 404."
    )


def test_supprimer_un_article_commente(client, alice, bob):
    article = creer_article(client, alice)
    commenter(client, bob, article["id"])
    response = client.delete(f"/api/articles/{article['id']}", headers=alice["headers"])
    assert response.status_code == 204, (
        f"Supprimer un article commenté doit répondre 204, pas {response.status_code} : "
        'ForeignKey("article.id", ondelete="CASCADE") sur Comment.article_id.'
    )


# La recherche


@pytest.fixture
def articles_varies(client, alice):
    for titre in ("Découvrir FastAPI", "Jinja2 en pratique", "fastapi et Pydantic"):
        creer_article(client, alice, titre)


@pytest.mark.parametrize("q", ["fastapi", "FASTAPI", "FastAPI"])
def test_recherche(client, articles_varies, q):
    response = client.get("/api/articles", params={"q": q})
    assert response.status_code == 200, "GET /api/articles?q=... doit répondre 200."
    titres = sorted(a["titre"] for a in response.json())
    assert titres == ["Découvrir FastAPI", "fastapi et Pydantic"], (
        f"?q={q} doit renvoyer les articles dont le titre contient « {q} », sans tenir compte "
        f"de la casse : {titres} reçus. Article.titre.icontains(q) (ou ilike)."
    )


def test_recherche_sans_resultat(client, articles_varies):
    assert client.get("/api/articles", params={"q": "django"}).json() == [], (
        "Une recherche sans résultat renvoie []."
    )


def test_recherche_paginee(client, articles_varies):
    premiere = client.get("/api/articles", params={"q": "fastapi", "limit": 1}).json()
    seconde = client.get(
        "/api/articles", params={"q": "fastapi", "limit": 1, "offset": 1}
    ).json()
    assert len(premiere) == 1 and len(seconde) == 1, (
        "La recherche doit accepter limit et offset."
    )
    assert {premiere[0]["titre"], seconde[0]["titre"]} == {
        "Découvrir FastAPI",
        "fastapi et Pydantic",
    }, (
        "Avec limit=1, offset=0 puis offset=1 doivent donner les deux résultats, un par page."
    )


def test_sans_q_la_liste_complete(client, articles_varies):
    assert len(client.get("/api/articles").json()) == 3, (
        "Sans q, la liste renvoie tous les articles."
    )


def test_service_search():
    articles = importer("app.services.articles", attendu_au="TP 8")
    assert hasattr(articles, "search"), (
        "La recherche vit dans app/services/articles.py : search(db, q, ...)."
    )
    assert (articles.search.__doc__ or "").strip(), (
        "search doit avoir sa docstring : au J4, c'est l'outil le plus utilisé par l'agent."
    )


# La base


def test_aucune_migration_en_attente():
    exiger("sqlalchemy", "alembic", "psycopg")
    from alembic import command
    from alembic.config import Config
    from alembic.util.exc import AutogenerateDiffsDetected, CommandError

    try:
        command.check(Config("alembic.ini"))
    except (AutogenerateDiffsDetected, CommandError) as exc:
        pytest.fail(
            f"{exc} : générez la migration du modèle Comment, puis alembic upgrade head.",
            pytrace=False,
        )
