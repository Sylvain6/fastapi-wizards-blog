"""Remplit la base avec des données de démonstration.

docker compose exec app uv run python -m scripts.seed

Le même script sert du TP 6 au TP 10 : il regarde ce que vos modèles contiennent
déjà et remplit ce qui existe (slug au TP 8, comptes et auteurs au TP 9,
commentaires au TP 10). Il ne dépend que des noms imposés par les énoncés.
"""

from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import delete

from app import models
from app.db import SessionLocal

NOMBRE_D_ARTICLES = 10
MOT_DE_PASSE = "password123"
COMPTES = ["alice@blog.fr", "bob@blog.fr", "admin@blog.fr"]
# deux titres connus, pour essayer la recherche ?q=fastapi au TP 10
TITRES_IMPOSES = [
    "Découvrir FastAPI en 10 minutes",
    "FastAPI et Pydantic, le duo gagnant",
]

fake = Faker("fr_FR")

Article = models.Article
User = getattr(models, "User", None)  # à partir du TP 9
Comment = getattr(models, "Comment", None)  # à partir du TP 10


def a_la_colonne(modele, colonne: str) -> bool:
    return colonne in modele.__table__.columns


def vider(db) -> None:
    """On repart de zéro à chaque lancement, enfants d'abord."""
    for modele in (Comment, Article, User):
        if modele is not None:
            db.execute(delete(modele))
    db.commit()


def creer_comptes(db) -> list:
    from pwdlib import PasswordHash

    hacheur = PasswordHash.recommended()
    comptes = [
        User(email=email, hashed_password=hacheur.hash(MOT_DE_PASSE))
        for email in COMPTES
    ]
    comptes[-1].is_admin = True  # admin@blog.fr : utile au TP 11
    db.add_all(comptes)
    db.flush()
    return comptes


def creer_articles(db, auteurs: list) -> list:
    if a_la_colonne(Article, "slug"):
        from app.services.slug import slugify
    deja_pris: set[str] = set()
    maintenant = datetime.now()
    articles = []
    for i in range(NOMBRE_D_ARTICLES):
        titre = (
            TITRES_IMPOSES[i]
            if i < len(TITRES_IMPOSES)
            else fake.sentence(nb_words=6).rstrip(".")
        )
        champs = {
            "titre": titre,
            "contenu": "\n\n".join(fake.paragraphs(nb=3)),
            "created_at": maintenant - timedelta(days=i),  # des dates distinctes
        }
        if a_la_colonne(Article, "slug"):
            slug, n = slugify(titre), 2
            while slug in deja_pris:  # le slug est unique
                slug, n = f"{slugify(titre)}-{n}", n + 1
            deja_pris.add(slug)
            champs["slug"] = slug
        if auteurs and a_la_colonne(Article, "author_id"):
            champs["author_id"] = auteurs[i % 2].id  # alice et bob écrivent
        articles.append(Article(**champs))
    db.add_all(articles)
    db.flush()
    return articles


def creer_commentaires(db, articles: list, auteurs: list) -> None:
    for i, article in enumerate(articles):
        for j in range(i % 3):  # 0, 1 ou 2 commentaires par article
            db.add(
                Comment(
                    contenu=fake.sentence(nb_words=12),
                    article_id=article.id,
                    author_id=auteurs[(i + j + 1) % 2].id,
                )
            )


def seed() -> None:
    with SessionLocal() as db:
        vider(db)
        comptes = creer_comptes(db) if User is not None else []
        auteurs = comptes[:2]
        articles = creer_articles(db, auteurs)
        if Comment is not None and auteurs:
            creer_commentaires(db, articles, auteurs)
        db.commit()
    bilan = f"{NOMBRE_D_ARTICLES} articles"
    if comptes:
        bilan = f"{len(COMPTES)} comptes (mot de passe : {MOT_DE_PASSE}), " + bilan
    if Comment is not None:
        bilan += " et leurs commentaires"
    print(f"{bilan} créés.")


if __name__ == "__main__":
    seed()
