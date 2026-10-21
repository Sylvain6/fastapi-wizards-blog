"""TP 7 : le CRUD des articles, et un formulaire HTML.

docker compose exec app uv run alembic upgrade head
docker compose exec app uv run pytest tests/validation/test_tp07.py
"""

import html
import re

import pytest

from tests.conftest import exiger, importer, route_declaree

VALIDE = {"titre": "Un titre correct", "contenu": "Un contenu assez long."}


def creer(client, **champs):
    response = client.post("/api/articles", json=VALIDE | champs)
    route_declaree(response, "POST /api/articles")
    assert response.status_code == 201, (
        f"POST /api/articles valide doit répondre 201, pas {response.status_code} : "
        f"{response.text[:200]}"
    )
    return response.json()


# Les schémas


def test_article_update_tout_optionnel():
    ArticleUpdate = importer("app.schemas.article", attendu_au="TP 3").__dict__.get(
        "ArticleUpdate"
    )
    assert ArticleUpdate is not None, (
        "app/schemas/article.py doit définir ArticleUpdate."
    )
    try:
        ArticleUpdate()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"ArticleUpdate() doit être valide sans aucun champ : tous optionnels ({exc}).",
            pytrace=False,
        )


def test_modele_a_publie():
    Article = importer("app.models.article", attendu_au="TP 5").Article
    assert "publie" in Article.__table__.columns, (
        "Le modèle Article doit avoir une colonne publie (False par défaut), "
        "avec sa migration."
    )


# POST /api/articles


def test_creation(client):
    article = creer(client)
    assert article["titre"] == VALIDE["titre"]
    assert article.get("publie") is False, (
        "Un article est non publié par défaut : publie=False."
    )
    assert "id" in article and "created_at" in article
    relu = client.get(f"/api/articles/{article['id']}")
    assert relu.status_code == 200, (
        "L'article créé doit être enregistré en base : db.commit()."
    )


def test_creation_publiee(client):
    assert creer(client, publie=True)["publie"] is True, (
        "publie=true doit être pris en compte."
    )


@pytest.mark.parametrize(
    "champs",
    [{"titre": "ab"}, {"titre": "x" * 256}, {"contenu": "trop court"[:9]}],
    ids=["titre de 2 caractères", "titre de 256 caractères", "contenu de 9 caractères"],
)
def test_creation_invalide(client, champs):
    response = client.post("/api/articles", json=VALIDE | champs)
    route_declaree(response, "POST /api/articles")
    assert response.status_code == 422, (
        f"POST /api/articles avec {champs} doit répondre 422 : "
        "titre = Field(min_length=3, max_length=255), contenu = Field(min_length=10)."
    )


def test_api_garde_son_422_json(client):
    response = client.post("/api/articles", json=VALIDE | {"titre": "ab"})
    assert response.headers["content-type"].startswith("application/json"), (
        "L'API doit garder son 422 en JSON : le handler ne réaffiche la page "
        "que pour la route du formulaire."
    )
    assert isinstance(response.json().get("detail"), list), (
        "Le 422 JSON doit lister les erreurs dans detail."
    )


# PATCH /api/articles/{id}


def test_patch_ne_modifie_que_les_champs_envoyes(client):
    article = creer(client, publie=True)
    response = client.patch(
        f"/api/articles/{article['id']}", json={"titre": "Nouveau titre"}
    )
    route_declaree(response, "PATCH /api/articles/{article_id}")
    assert response.status_code == 200, "PATCH /api/articles/{id} doit répondre 200."
    modifie = response.json()
    assert modifie["titre"] == "Nouveau titre", "Le titre envoyé doit être modifié."
    assert modifie["contenu"] == VALIDE["contenu"], (
        "Le contenu, non envoyé, ne doit pas changer : model_dump(exclude_unset=True)."
    )
    assert modifie["publie"] is True, (
        "publie, non envoyé, ne doit pas revenir à False : model_dump(exclude_unset=True)."
    )
    assert (
        client.get(f"/api/articles/{article['id']}").json()["titre"] == "Nouveau titre"
    ), "La modification doit être enregistrée : db.commit()."


def test_patch_invalide(client):
    article = creer(client)
    response = client.patch(f"/api/articles/{article['id']}", json={"titre": "ab"})
    assert response.status_code == 422, (
        "Un PATCH garde les mêmes contraintes : titre de 2 caractères → 422."
    )


def test_patch_introuvable(client):
    response = client.patch("/api/articles/999", json={"titre": "Nouveau titre"})
    route_declaree(response, "PATCH /api/articles/{article_id}")
    assert response.status_code == 404, (
        "PATCH sur un article inexistant doit répondre 404."
    )


# DELETE /api/articles/{id}


def test_suppression(client):
    article = creer(client)
    response = client.delete(f"/api/articles/{article['id']}")
    route_declaree(response, "DELETE /api/articles/{article_id}")
    assert response.status_code == 204, "DELETE doit répondre 204 : status_code=204."
    assert response.content == b"", "Une réponse 204 n'a pas de corps."
    assert client.get(f"/api/articles/{article['id']}").status_code == 404, (
        "Après DELETE, l'article ne doit plus exister : db.delete(article) puis db.commit()."
    )


def test_suppression_introuvable(client):
    response = client.delete("/api/articles/999")
    route_declaree(response, "DELETE /api/articles/{article_id}")
    assert response.status_code == 404, (
        "DELETE sur un article inexistant doit répondre 404."
    )


# Le formulaire HTML


def test_page_formulaire(client):
    response = client.get("/articles/new")
    assert response.status_code != 422, (
        "GET /articles/new répond 422 : « new » est lu comme un article_id. "
        "Déclarez /articles/new AVANT /articles/{article_id}."
    )
    route_declaree(response, "GET /articles/new")
    assert response.status_code == 200, "GET /articles/new doit répondre 200."
    page = response.text
    assert "<form" in page and re.search(r'method="post"', page, re.IGNORECASE), (
        'La page doit contenir un <form method="post">.'
    )
    for champ in ("titre", "contenu"):
        assert f'name="{champ}"' in page, (
            f'Le formulaire doit avoir un champ name="{champ}".'
        )


def test_formulaire_valide_redirige(client):
    response = client.post("/articles/new", data=VALIDE, follow_redirects=False)
    route_declaree(response, "POST /articles/new")
    assert response.status_code == 303, (
        f"Un formulaire valide doit rediriger en 303, pas {response.status_code} : "
        "RedirectResponse(url, status_code=303)."
    )
    cible = response.headers.get("location", "")
    trouve = re.search(r"/articles/(\d+)$", cible)
    assert trouve, (
        f"La redirection doit mener à la page de l'article (/articles/<id>), pas à « {cible} »."
    )
    article = client.get(f"/api/articles/{trouve.group(1)}")
    assert article.status_code == 200 and article.json()["titre"] == VALIDE["titre"], (
        "L'article du formulaire doit être enregistré en base."
    )


def test_formulaire_invalide_se_reaffiche(client):
    saisie = {"titre": "ab", "contenu": "Un contenu bien saisi."}
    response = client.post("/articles/new", data=saisie, follow_redirects=False)
    route_declaree(response, "POST /articles/new")
    assert response.headers["content-type"].startswith("text/html"), (
        "Un formulaire invalide doit réafficher la page HTML, pas un JSON : "
        "un exception_handler sur RequestValidationError rend le template."
    )
    assert response.status_code == 422, "La page réaffichée doit garder le statut 422."
    page = html.unescape(response.text)
    assert "<form" in page, "La page réaffichée doit contenir le formulaire."
    assert saisie["contenu"] in page and 'value="ab"' in page, (
        "Le formulaire réaffiché doit garder les valeurs saisies."
    )
    vide = html.unescape(client.get("/articles/new").text)
    assert len(page) > len(vide) + len(saisie["contenu"]) + 10, (
        "Le formulaire réaffiché doit afficher un message d'erreur."
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
            f"{exc} : générez la migration de publie "
            "(alembic revision --autogenerate -m publie) puis alembic upgrade head.",
            pytrace=False,
        )


def test_liste_toujours_la(client):
    route_declaree(client.get("/api/articles"), "GET /api/articles (TP 6)")
