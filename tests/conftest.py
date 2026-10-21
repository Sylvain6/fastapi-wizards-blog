"""Fixtures partagées : suites de validation et vos propres tests. Ne pas modifier."""

import importlib
import importlib.util

import pytest
from fastapi.testclient import TestClient


def module_present(nom):
    try:
        return importlib.util.find_spec(nom) is not None
    except ModuleNotFoundError:
        return False


def exiger(*paquets):
    """Échoue avec la commande uv add à lancer si un paquet manque."""
    manquants = [p for p in paquets if not module_present(p)]
    if manquants:
        commande = 'uv add sqlalchemy alembic "psycopg[binary]" pydantic-settings'
        pytest.fail(
            f"Paquet(s) absent(s) : {', '.join(manquants)}. "
            f"Installez-les : docker compose exec app {commande}",
            pytrace=False,
        )


def importer(nom, *, attendu_au):
    if not module_present(nom):
        pytest.fail(
            f"Le module {nom} est absent : il s'écrit au {attendu_au}.", pytrace=False
        )
    try:
        return importlib.import_module(nom)
    except Exception as exc:  # noqa: BLE001 : toute erreur d'import de l'élève doit s'afficher
        pytest.fail(f"Impossible d'importer {nom} : {exc!r}", pytrace=False)


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
def session_factory():
    """Une fabrique de sessions sur une base SQLite en mémoire, vide à chaque test."""
    exiger("sqlalchemy")
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    db = importer("app.db", attendu_au="TP 5")
    if module_present("app.models"):
        importer("app.models", attendu_au="TP 5")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def activer_les_cles_etrangeres(connexion, _):
        connexion.execute("PRAGMA foreign_keys=ON")

    db.Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    db.Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def client(request):
    try:
        from app.main import app
    except Exception as exc:  # noqa: BLE001 : toute erreur d'import de l'élève doit s'afficher
        pytest.fail(f"Impossible d'importer app.main:app : {exc!r}", pytrace=False)

    # À partir du TP 5, les routes utilisent la base de test, jamais Postgres
    if module_present("app.db"):
        db = importer("app.db", attendu_au="TP 5")
        if not hasattr(db, "get_session_factory"):
            pytest.fail(
                "app/db.py doit définir la dépendance get_session_factory().",
                pytrace=False,
            )
        factory = request.getfixturevalue("session_factory")
        app.dependency_overrides[db.get_session_factory] = lambda: factory

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# À partir du TP 9 : des comptes connectés

MOT_DE_PASSE = "motdepasse123"


def compte(client, email):
    """Inscrit un compte et renvoie ses infos, avec son jeton et l'en-tête à envoyer."""
    inscription = client.post(
        "/auth/register", json={"email": email, "password": MOT_DE_PASSE}
    )
    route_declaree(inscription, "POST /auth/register (TP 9)")
    assert inscription.status_code == 201, (
        f"Inscription impossible : {inscription.text[:200]}"
    )
    connexion = client.post(
        "/auth/token", data={"username": email, "password": MOT_DE_PASSE}
    )
    assert connexion.status_code == 200, (
        f"Connexion impossible : {connexion.text[:200]}"
    )
    token = connexion.json()["access_token"]
    return inscription.json() | {
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def alice(client):
    return compte(client, "alice@blog.fr")


@pytest.fixture
def bob(client):
    return compte(client, "bob@blog.fr")
