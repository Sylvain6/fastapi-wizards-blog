"""TP 9 : inscription, connexion et droits d'auteur.

docker compose down -v && docker compose up -d
docker compose exec app uv run alembic upgrade head
docker compose exec app uv run python -m scripts.seed
docker compose exec app uv run pytest tests/validation/test_tp09.py
"""

import inspect
import re
from datetime import UTC, datetime

import pytest

from tests.conftest import exiger, importer, route_declaree

MOT_DE_PASSE = "motdepasse123"
ARTICLE = {"titre": "Un titre correct", "contenu": "Un contenu assez long."}


def inscrire(client, email):
    response = client.post(
        "/auth/register", json={"email": email, "password": MOT_DE_PASSE}
    )
    route_declaree(response, "POST /auth/register")
    assert response.status_code == 201, (
        f"POST /auth/register doit répondre 201, pas {response.status_code} : {response.text[:200]}"
    )
    return response.json()


def jeton(client, email):
    response = client.post(
        "/auth/token", data={"username": email, "password": MOT_DE_PASSE}
    )
    route_declaree(response, "POST /auth/token")
    assert response.status_code == 200, (
        f"POST /auth/token doit répondre 200, pas {response.status_code} : {response.text[:200]}. "
        "Il lit un formulaire (OAuth2PasswordRequestForm), l'email dans username."
    )
    corps = response.json()
    assert "access_token" in corps, 'La réponse doit contenir "access_token".'
    return corps["access_token"]


def entete(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice(client):
    utilisateur = inscrire(client, "alice@blog.fr")
    return utilisateur | {"token": jeton(client, "alice@blog.fr")}


@pytest.fixture
def bob(client):
    utilisateur = inscrire(client, "bob@blog.fr")
    return utilisateur | {"token": jeton(client, "bob@blog.fr")}


def ne_contient_aucun_mot_de_passe(response):
    texte = response.text
    assert "hashed_password" not in texte and MOT_DE_PASSE not in texte, (
        f"La réponse de {response.request.method} {response.request.url.path} contient "
        "le mot de passe ou son hash : renvoyez un UserPublic (id, email, is_admin)."
    )


# Inscription


def test_inscription(client):
    response = client.post(
        "/auth/register", json={"email": "c@blog.fr", "password": MOT_DE_PASSE}
    )
    route_declaree(response, "POST /auth/register")
    assert response.status_code == 201, "POST /auth/register doit répondre 201."
    utilisateur = response.json()
    assert utilisateur.get("email") == "c@blog.fr" and "id" in utilisateur
    assert utilisateur.get("is_admin") is False, (
        "Un nouvel inscrit n'est pas administrateur."
    )
    ne_contient_aucun_mot_de_passe(response)


def test_email_deja_pris(client):
    inscrire(client, "c@blog.fr")
    response = client.post(
        "/auth/register", json={"email": "c@blog.fr", "password": MOT_DE_PASSE}
    )
    assert response.status_code == 409, (
        f"Un email déjà pris doit répondre 409, pas {response.status_code} : "
        "le service lève une exception, le router (ou un exception_handler) la traduit."
    )


def test_email_invalide(client):
    response = client.post(
        "/auth/register", json={"email": "pas-un-email", "password": MOT_DE_PASSE}
    )
    route_declaree(response, "POST /auth/register")
    assert response.status_code == 422, (
        "Un email invalide doit répondre 422 : typez-le en EmailStr."
    )


def test_mot_de_passe_hache(client, db):
    utilisateur = inscrire(client, "c@blog.fr")
    User = importer("app.models.user", attendu_au="TP 9").User
    db.expire_all()
    en_base = db.get(User, utilisateur["id"])
    assert en_base.hashed_password != MOT_DE_PASSE, (
        "Le mot de passe ne doit jamais être stocké en clair."
    )
    assert en_base.hashed_password.startswith("$argon2"), (
        "Le mot de passe doit être haché avec pwdlib (argon2) : PasswordHash.recommended()."
    )


def test_modele_user():
    User = importer("app.models.user", attendu_au="TP 9").User
    colonnes = User.__table__.columns
    for nom in ("id", "email", "hashed_password", "is_admin"):
        assert nom in colonnes, f"Le modèle User doit avoir une colonne {nom}."
    email = colonnes["email"]
    assert email.unique or any(
        i.unique and "email" in i.columns for i in User.__table__.indexes
    ), "La colonne email doit être unique."


# Jeton


def test_jeton(client, alice):
    jwt = importer("jwt", attendu_au="TP 9 (uv add pyjwt)")
    settings = importer("app.config", attendu_au="TP 5").settings
    try:
        contenu = jwt.decode(alice["token"], settings.secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        pytest.fail(
            f"Le jeton ne se décode pas avec SECRET_KEY en HS256 : {exc}", pytrace=False
        )
    assert contenu.get("sub") == str(alice["id"]), (
        "Le jeton doit contenir l'id de l'utilisateur en chaîne : {\"sub\": str(user.id)}."
    )
    assert "exp" in contenu, "Le jeton doit avoir une expiration (exp)."
    minutes = (
        datetime.fromtimestamp(contenu["exp"], UTC) - datetime.now(UTC)
    ).total_seconds() / 60
    assert 25 <= minutes <= 31, (
        f"Le jeton doit expirer dans 30 minutes, pas {minutes:.0f}."
    )


def test_jeton_type_bearer(client, alice):
    response = client.post(
        "/auth/token", data={"username": "alice@blog.fr", "password": MOT_DE_PASSE}
    )
    assert response.json().get("token_type", "").lower() == "bearer", (
        'La réponse doit contenir "token_type": "bearer".'
    )


@pytest.mark.parametrize(
    ("username", "password"),
    [("alice@blog.fr", "mauvais-mot-de-passe"), ("inconnu@blog.fr", MOT_DE_PASSE)],
    ids=["mauvais mot de passe", "email inconnu"],
)
def test_jeton_refuse(client, alice, username, password):
    response = client.post(
        "/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 401, (
        "Des identifiants invalides doivent répondre 401."
    )


def test_jeton_attend_un_formulaire(client, alice):
    response = client.post(
        "/auth/token", json={"username": "alice@blog.fr", "password": MOT_DE_PASSE}
    )
    assert response.status_code == 422, (
        "POST /auth/token reçoit un formulaire, pas du JSON : OAuth2PasswordRequestForm."
    )


def test_bouton_authorize(client):
    schemas = (
        client.get("/openapi.json")
        .json()
        .get("components", {})
        .get("securitySchemes", {})
    )
    flux = [
        s.get("flows", {}).get("password", {}).get("tokenUrl", "")
        for s in schemas.values()
    ]
    assert any(url.endswith("/auth/token") for url in flux), (
        'Le bouton Authorize de /docs doit pointer vers /auth/token : OAuth2PasswordBearer(tokenUrl="/auth/token").'
    )


# Utilisateur connecté


def test_me(client, alice):
    response = client.get("/auth/me", headers=entete(alice["token"]))
    route_declaree(response, "GET /auth/me")
    assert response.status_code == 200, "GET /auth/me avec un jeton doit répondre 200."
    assert response.json().get("email") == "alice@blog.fr"
    ne_contient_aucun_mot_de_passe(response)


@pytest.mark.parametrize(
    "entetes",
    [{}, {"Authorization": "Bearer nimporte.quoi.ici"}],
    ids=["sans jeton", "jeton invalide"],
)
def test_me_sans_jeton_valide(client, entetes):
    response = client.get("/auth/me", headers=entetes)
    route_declaree(response, "GET /auth/me")
    assert response.status_code == 401, (
        "GET /auth/me sans jeton valide doit répondre 401 : get_current_user."
    )


# Droits sur les articles


def test_creer_exige_d_etre_connecte(client):
    response = client.post("/api/articles", json=ARTICLE)
    route_declaree(response, "POST /api/articles")
    assert response.status_code == 401, "Créer un article sans jeton doit répondre 401."


def test_l_article_appartient_a_son_auteur(client, db, alice):
    response = client.post(
        "/api/articles", json=ARTICLE, headers=entete(alice["token"])
    )
    assert response.status_code == 201, (
        f"Créer un article avec un jeton doit répondre 201 : {response.text[:200]}"
    )
    Article = importer("app.models.article", attendu_au="TP 5").Article
    assert "author_id" in Article.__table__.columns, (
        "Le modèle Article doit avoir une colonne author_id."
    )
    db.expire_all()
    assert db.get(Article, response.json()["id"]).author_id == alice["id"], (
        "author_id doit être l'utilisateur du jeton : create_article(db, data, author)."
    )


def test_modifier_son_article(client, alice):
    article = client.post(
        "/api/articles", json=ARTICLE, headers=entete(alice["token"])
    ).json()
    response = client.patch(
        f"/api/articles/{article['id']}",
        json={"titre": "Titre modifié"},
        headers=entete(alice["token"]),
    )
    assert response.status_code == 200, (
        "L'auteur doit pouvoir modifier son article (200)."
    )


def test_modifier_l_article_d_un_autre(client, alice, bob):
    article = client.post(
        "/api/articles", json=ARTICLE, headers=entete(alice["token"])
    ).json()
    response = client.patch(
        f"/api/articles/{article['id']}",
        json={"titre": "Titre modifié"},
        headers=entete(bob["token"]),
    )
    assert response.status_code == 403, (
        f"Modifier l'article d'un autre doit répondre 403, pas {response.status_code}."
    )
    sans_jeton = client.patch(
        f"/api/articles/{article['id']}", json={"titre": "Titre modifié"}
    )
    assert sans_jeton.status_code == 401, (
        "Modifier un article sans jeton doit répondre 401."
    )


def test_supprimer(client, alice, bob):
    article = client.post(
        "/api/articles", json=ARTICLE, headers=entete(alice["token"])
    ).json()
    autre = client.delete(
        f"/api/articles/{article['id']}", headers=entete(bob["token"])
    )
    assert autre.status_code == 403, "Supprimer l'article d'un autre doit répondre 403."
    auteur = client.delete(
        f"/api/articles/{article['id']}", headers=entete(alice["token"])
    )
    assert auteur.status_code == 204, (
        "L'auteur doit pouvoir supprimer son article (204)."
    )


def test_lecture_publique(client, alice):
    client.post("/api/articles", json=ARTICLE, headers=entete(alice["token"]))
    assert client.get("/api/articles").status_code == 200, (
        "La liste des articles reste publique."
    )


def test_services_recoivent_l_utilisateur():
    articles = importer("app.services.articles", attendu_au="TP 8")
    parametres = inspect.signature(articles.create_article).parameters
    assert len(parametres) >= 3, (
        "create_article reçoit l'utilisateur en paramètre : create_article(db, data, author). "
        "Au J4, l'agent l'appellera avec l'utilisateur connecté."
    )


# Pages HTML et cookie


def test_page_de_connexion(client):
    response = client.get("/login")
    route_declaree(response, "GET /login")
    assert response.status_code == 200 and "<form" in response.text, (
        "GET /login doit afficher un formulaire."
    )


def test_connexion_pose_un_cookie(client, alice):
    response = client.post(
        "/login",
        data={"username": "alice@blog.fr", "password": MOT_DE_PASSE},
        follow_redirects=False,
    )
    route_declaree(response, "POST /login")
    assert response.status_code == 303, (
        f"POST /login doit rediriger en 303, pas {response.status_code}."
    )
    cookie = response.headers.get("set-cookie", "")
    assert cookie.startswith("access_token="), (
        "POST /login doit poser le cookie access_token."
    )
    assert "httponly" in cookie.lower(), (
        "Le cookie doit être httponly : le JavaScript ne peut pas le lire."
    )


def test_connexion_refusee(client, alice):
    response = client.post(
        "/login",
        data={"username": "alice@blog.fr", "password": "mauvais"},
        follow_redirects=False,
    )
    assert "access_token=" not in response.headers.get("set-cookie", ""), (
        "Des identifiants invalides ne doivent pas poser de cookie."
    )


def test_formulaire_avec_le_cookie(client, db, alice):
    client.post(
        "/login",
        data={"username": "alice@blog.fr", "password": MOT_DE_PASSE},
        follow_redirects=False,
    )
    response = client.post("/articles/new", data=ARTICLE, follow_redirects=False)
    assert response.status_code == 303, (
        f"Connecté par cookie, le formulaire doit créer l'article (303), pas {response.status_code} : "
        "get_current_user lit l'en-tête Bearer, sinon le cookie access_token."
    )
    Article = importer("app.models.article", attendu_au="TP 5").Article
    article_id = int(
        re.search(r"/articles/(\d+)$", response.headers["location"]).group(1)
    )
    db.expire_all()
    assert db.get(Article, article_id).author_id == alice["id"], (
        "L'article du formulaire appartient à l'utilisateur du cookie."
    )


def test_formulaire_sans_cookie(client):
    response = client.get("/articles/new", follow_redirects=False)
    route_declaree(response, "GET /articles/new")
    assert response.status_code != 200, (
        "Sans être connecté, /articles/new ne doit pas afficher le formulaire : redirigez vers /login."
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
            f"{exc} : générez la migration (user, author_id), puis docker compose down -v, "
            "docker compose up -d, alembic upgrade head et le seed.",
            pytrace=False,
        )
