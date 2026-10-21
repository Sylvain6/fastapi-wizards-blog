"""TP 4 : routing et paramètres.

docker compose exec app uv run pytest tests/validation/test_tp04.py
"""

import json
import re
import uuid
from decimal import Decimal

import pytest


def texte(response):
    """Le contenu de la réponse, qu'elle soit en JSON ou en texte brut."""
    try:
        return json.dumps(response.json(), ensure_ascii=False)
    except ValueError:
        return response.text


def route_declaree(response, route):
    if response.status_code in (404, 405):
        pytest.fail(
            f"{route} répond {response.status_code} : la route est-elle déclarée ?",
            pytrace=False,
        )


def operation(client, methode, motif):
    """L'opération OpenAPI dont le chemin correspond au motif (ex. /products/{...})."""
    for chemin, operations in client.get("/openapi.json").json()["paths"].items():
        if re.fullmatch(motif, chemin) and methode in operations:
            return operations[methode]
    pytest.fail(
        f"Aucune route {methode.upper()} {motif} dans /docs : est-elle déclarée, "
        "et le router est-il inclus avec app.include_router(...) ?",
        pytrace=False,
    )


PARAM = r"\{[^}]+\}"
ROUTES = [
    ("get", rf"/products/{PARAM}"),
    ("get", r"/search"),
    ("get", rf"/categories/{PARAM}"),
    ("get", r"/products/new"),
    ("post", r"/products"),
    ("get", rf"/sizes/{PARAM}"),
    ("get", rf"/sessions/{PARAM}"),
    ("get", rf"/debug/{PARAM}"),
]


def test_router_dans_son_fichier():
    try:
        from app.routers.exercices import router
    except ImportError as exc:
        pytest.fail(
            f"app/routers/exercices.py doit définir router = APIRouter(...) ({exc}). "
            "Le dossier app/routers/ a-t-il un __init__.py ?",
            pytrace=False,
        )
    assert router.routes, (
        "Le router d'app/routers/exercices.py ne contient aucune route."
    )


NOMS = [
    "GET /products/{id}",
    "GET /search",
    "GET /categories/{name}",
    "GET /products/new",
    "POST /products",
    "GET /sizes/{size}",
    "GET /sessions/{uuid}",
    "GET /debug/{value}",
]


@pytest.mark.parametrize(("methode", "motif"), ROUTES, ids=NOMS)
def test_route_sous_le_tag_exercices(client, methode, motif):
    tags = operation(client, methode, motif).get("tags", [])
    assert "exercices" in tags, (
        f"{methode.upper()} {motif} doit apparaître sous le tag « exercices » : "
        'APIRouter(tags=["exercices"]).'
    )


# 1. /products/{id}


def test_produit(client):
    response = client.get("/products/5")
    route_declaree(response, "GET /products/5")
    assert response.status_code == 200, "GET /products/5 doit répondre 200."
    assert "Produit n°5" in texte(response), (
        "GET /products/5 doit renvoyer « Produit n°5 »."
    )


@pytest.mark.parametrize("valeur", ["0", "-1", "abc", "1.5"])
def test_produit_invalide(client, valeur):
    response = client.get(f"/products/{valeur}")
    route_declaree(response, f"GET /products/{valeur}")
    assert response.status_code == 422, (
        f"GET /products/{valeur} doit répondre 422 : l'id est un entier ≥ 1, "
        "Annotated[int, Path(ge=1)]."
    )


# 2. /search


def test_recherche(client):
    response = client.get("/search", params={"q": "fastapi"})
    route_declaree(response, "GET /search")
    assert response.status_code == 200, "GET /search?q=fastapi doit répondre 200."
    assert client.get("/search", params={"q": "abc", "limit": 50}).status_code == 200, (
        "limit=50 est autorisé."
    )


@pytest.mark.parametrize(
    "params",
    [{}, {"q": "ab"}, {"q": "fastapi", "limit": 51}, {"q": "fastapi", "limit": "dix"}],
    ids=["sans q", "q trop court", "limit au-delà de 50", "limit non entier"],
)
def test_recherche_invalide(client, params):
    response = client.get("/search", params=params)
    route_declaree(response, "GET /search")
    assert response.status_code == 422, f"GET /search avec {params} doit répondre 422."


def test_recherche_documentee(client):
    parametres = {
        p["name"]: p for p in operation(client, "get", "/search")["parameters"]
    }
    assert "q" in parametres and "limit" in parametres, (
        "/search doit avoir les paramètres de requête q et limit."
    )
    q, limit = parametres["q"], parametres["limit"]
    assert q.get("required"), "q doit être obligatoire : pas de valeur par défaut."
    assert q["schema"].get("minLength") == 3, "q doit faire 3 caractères minimum."
    assert limit["schema"].get("default") == 10, "limit doit valoir 10 par défaut."
    assert limit["schema"].get("maximum") == 50, "limit doit valoir 50 au maximum."


# 3. /categories/{name}


def test_categorie_sans_pays(client):
    response = client.get("/categories/livres")
    route_declaree(response, "GET /categories/livres")
    assert response.status_code == 200, "GET /categories/livres doit répondre 200."
    assert "non précisé" in texte(response), (
        "Sans country, renvoyer « Pays : non précisé »."
    )


@pytest.mark.parametrize("pays", ["fr", "en"])
def test_categorie_avec_pays(client, pays):
    response = client.get("/categories/livres", params={"country": pays})
    route_declaree(response, "GET /categories/livres")
    assert response.status_code == 200, f"country={pays} est autorisé."
    assert pays in texte(response), (
        f"Avec country={pays}, la réponse doit indiquer le pays."
    )


def test_categorie_pays_invalide(client):
    response = client.get("/categories/livres", params={"country": "de"})
    route_declaree(response, "GET /categories/livres")
    assert response.status_code == 422, (
        'country=de doit répondre 422 : Literal["fr", "en"] | None.'
    )


# 4. /products/new


def test_nouveau_produit(client):
    response = client.get("/products/new")
    assert response.status_code != 422, (
        "GET /products/new répond 422 : « new » est lu comme un id. "
        "Déclarez /products/new AVANT /products/{id}."
    )
    route_declaree(response, "GET /products/new")
    assert "Nouveau produit" in texte(response), (
        "GET /products/new doit renvoyer « Nouveau produit »."
    )


# 5. POST /products


def test_creation_produit(client):
    response = client.post("/products", json={"name": "Grimoire", "price": "12.50"})
    route_declaree(response, "POST /products")
    assert response.status_code == 201, "POST /products doit répondre 201."
    produit = response.json()
    assert produit.get("name") == "Grimoire", "Le produit renvoyé doit reprendre name."
    assert Decimal(str(produit.get("price"))) == Decimal("12.50"), (
        "Le produit renvoyé doit reprendre price."
    )


@pytest.mark.parametrize(
    "corps",
    [
        {"name": "Grimoire", "price": "0"},
        {"name": "Grimoire", "price": "-3"},
        {"name": "Grimoire", "price": "12.345"},
        {"price": "12.50"},
        {"name": "Grimoire"},
    ],
    ids=["prix nul", "prix négatif", "3 décimales", "sans name", "sans price"],
)
def test_creation_produit_invalide(client, corps):
    response = client.post("/products", json=corps)
    route_declaree(response, "POST /products")
    assert response.status_code == 422, (
        f"POST /products avec {corps} doit répondre 422 : "
        "price: Decimal = Field(gt=0, decimal_places=2)."
    )


# 6. /sizes/{size}


@pytest.mark.parametrize("taille", ["small", "medium", "large"])
def test_taille(client, taille):
    response = client.get(f"/sizes/{taille}")
    route_declaree(response, f"GET /sizes/{taille}")
    assert response.status_code == 200, f"GET /sizes/{taille} doit répondre 200."


def test_taille_invalide(client):
    response = client.get("/sizes/xl")
    route_declaree(response, "GET /sizes/xl")
    assert response.status_code == 422, (
        "GET /sizes/xl doit répondre 422 : la taille est un Enum (small, medium, large)."
    )


# 7. /sessions/{uuid}


def test_session(client):
    identifiant = str(uuid.uuid4())
    response = client.get(f"/sessions/{identifiant}")
    route_declaree(response, "GET /sessions/{uuid}")
    assert response.status_code == 200, "GET /sessions/<un UUID> doit répondre 200."
    assert identifiant in texte(response), "La réponse doit contenir l'UUID reçu."


def test_session_invalide(client):
    response = client.get("/sessions/pas-un-uuid")
    route_declaree(response, "GET /sessions/pas-un-uuid")
    assert response.status_code == 422, (
        "GET /sessions/pas-un-uuid doit répondre 422 : typez-le en UUID."
    )


# 8. /debug/{value}


def test_debug(client):
    response = client.get(
        "/debug/abracadabra", headers={"User-Agent": "navigateur-de-test"}
    )
    route_declaree(response, "GET /debug/abracadabra")
    assert response.status_code == 200, "GET /debug/abracadabra doit répondre 200."
    contenu = texte(response)
    attendus = {
        "la value": "abracadabra",
        "la méthode HTTP": "GET",
        "l'URL complète": "http://testserver/debug/abracadabra",
        "l'en-tête User-Agent": "navigateur-de-test",
    }
    for quoi, valeur in attendus.items():
        assert valeur in contenu, (
            f"/debug doit renvoyer {quoi} ({valeur}) : lisez-la dans Request."
        )


# Les TP précédents


def test_articles_toujours_la(client):
    response = client.get("/api/articles")
    route_declaree(response, "GET /api/articles (TP 3)")
