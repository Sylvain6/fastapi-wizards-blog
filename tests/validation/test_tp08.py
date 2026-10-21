"""TP 8 : extraire un service.

docker compose down -v && docker compose up -d
docker compose exec app uv run alembic upgrade head
docker compose exec app uv run python -m scripts.seed
docker compose exec app uv run pytest tests/validation/test_tp08.py
"""

import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import exiger, importer, route_declaree


def slugify():
    return importer("app.services.slug", attendu_au="TP 8").__dict__.get(
        "slugify"
    ) or pytest.fail(
        "app/services/slug.py doit définir slugify(titre: str) -> str.", pytrace=False
    )


@pytest.mark.parametrize(
    ("titre", "attendu"),
    [
        ("Été à Paris !", "ete-a-paris"),
        ("Bonjour", "bonjour"),
        ("  Plusieurs   espaces  ", "plusieurs-espaces"),
        ("C'est l'été, en 2026 !", "c-est-l-ete-en-2026"),
        ("Ça marche ? Oui !!", "ca-marche-oui"),
        ("déjà-propre", "deja-propre"),
    ],
    ids=[
        "accents et ponctuation",
        "mot simple",
        "espaces",
        "apostrophes",
        "cedille",
        "deja propre",
    ],
)
def test_slugify(titre, attendu):
    obtenu = slugify()(titre)
    assert obtenu == attendu, (
        f"slugify({titre!r}) donne {obtenu!r}, {attendu!r} attendu : minuscules, accents "
        "retirés, chaque suite de caractères non alphanumériques remplacée par un tiret, "
        "pas de tiret au début ni à la fin."
    )


def fonctions_publiques(module):
    return [
        (nom, objet)
        for nom, objet in inspect.getmembers(module, inspect.isfunction)
        if objet.__module__ == module.__name__ and not nom.startswith("_")
    ]


@pytest.mark.parametrize("nom", ["app.services.slug", "app.services.articles"])
def test_chaque_fonction_de_service_a_sa_docstring(nom):
    module = importer(nom, attendu_au="TP 8")
    fonctions = fonctions_publiques(module)
    assert fonctions, f"{nom} ne définit aucune fonction."
    sans_doc = [f for f, objet in fonctions if not (objet.__doc__ or "").strip()]
    assert not sans_doc, (
        f"Ces fonctions de {nom} n'ont pas de docstring : {', '.join(sans_doc)}. "
        "Une phrase suffit : au J4, un agent la lira pour savoir à quoi sert l'outil."
    )


def test_service_create_article():
    articles = importer("app.services.articles", attendu_au="TP 8")
    assert hasattr(articles, "create_article"), (
        "app/services/articles.py doit définir create_article(db, data)."
    )


def test_services_ignorent_http():
    fichiers = list(Path("app/services").glob("*.py"))
    assert fichiers, "Le dossier app/services/ est vide ou absent."
    for fichier in fichiers:
        source = fichier.read_text()
        for interdit in ("HTTPException", "Request", "fastapi"):
            assert interdit not in source, (
                f"{fichier} mentionne {interdit} : un service ne connaît pas HTTP. "
                "Il lève une exception métier, que le router (ou un exception_handler) traduit."
            )


def test_colonne_slug_unique():
    Article = importer("app.models.article", attendu_au="TP 5").Article
    colonnes = Article.__table__.columns
    assert "slug" in colonnes, "Le modèle Article doit avoir une colonne slug."
    slug = colonnes["slug"]
    unique = slug.unique or any(
        index.unique and "slug" in index.columns for index in Article.__table__.indexes
    )
    assert unique, (
        "La colonne slug doit être unique : mapped_column(String(255), unique=True)."
    )
    assert not slug.nullable, "La colonne slug ne doit pas être nullable."


def slug_en_base(db, article_id):
    Article = importer("app.models.article", attendu_au="TP 5").Article
    if "slug" not in Article.__table__.columns:
        pytest.fail("Le modèle Article n'a pas encore de colonne slug.", pytrace=False)
    db.expire_all()
    article = db.get(Article, article_id)
    assert article is not None, f"L'article {article_id} est introuvable en base."
    return article.slug


def test_creation_api_remplit_le_slug(client, db):
    response = client.post(
        "/api/articles",
        json={"titre": "Été à Paris !", "contenu": "Un contenu assez long."},
    )
    route_declaree(response, "POST /api/articles")
    assert response.status_code == 201, (
        f"POST /api/articles doit répondre 201 : {response.text[:200]}"
    )
    assert slug_en_base(db, response.json()["id"]) == "ete-a-paris", (
        "À la création, le slug doit être calculé à partir du titre : slugify(data.titre)."
    )


def test_creation_formulaire_remplit_le_slug(client, db):
    response = client.post(
        "/articles/new",
        data={"titre": "Ça marche ? Oui !!", "contenu": "Un contenu assez long."},
        follow_redirects=False,
    )
    route_declaree(response, "POST /articles/new")
    assert response.status_code == 303, (
        f"Le formulaire doit rediriger en 303 : {response.text[:200]}"
    )
    article_id = re.search(r"/articles/(\d+)$", response.headers["location"]).group(1)
    assert slug_en_base(db, int(article_id)) == "ca-marche-oui", (
        "Le formulaire doit aussi remplir le slug : il appelle le même service que l'API."
    )


def test_routes_sans_logique_de_creation():
    fautifs = [
        str(fichier)
        for fichier in Path("app/routers").glob("*.py")
        if re.search(r"\b\w+\.add\(", fichier.read_text())
    ]
    assert not fautifs, (
        f"Ces routers créent encore des objets eux-mêmes (db.add) : {', '.join(fautifs)}. "
        "La création passe par services.articles.create_article(db, data)."
    )


def test_introuvable_toujours_404(client):
    response = client.get("/api/articles/999")
    route_declaree(response, "GET /api/articles/{article_id}")
    assert response.status_code == 404, (
        "GET /api/articles/999 doit toujours répondre 404."
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
            f"{exc} : générez la migration du slug (alembic revision --autogenerate -m slug), "
            "puis docker compose down -v, docker compose up -d, alembic upgrade head.",
            pytrace=False,
        )


def test_seed_remplit_les_slugs():
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
        "Le seed doit donner un slug à chaque article (ou passer par create_article)."
    )
    from sqlalchemy import func, select

    db = importer("app.db", attendu_au="TP 5")
    Article = importer("app.models.article", attendu_au="TP 5").Article
    if "slug" not in Article.__table__.columns:
        pytest.fail("Le modèle Article n'a pas encore de colonne slug.", pytrace=False)
    with db.SessionLocal() as session:
        sans_slug = session.scalar(
            select(func.count()).select_from(Article).where(Article.slug.is_(None))
        )
        total = session.scalar(select(func.count()).select_from(Article))
    assert total >= 10, (
        f"Après le seed, Postgres contient {total} articles : 10 attendus."
    )
    assert sans_slug == 0, f"{sans_slug} articles n'ont pas de slug après le seed."
