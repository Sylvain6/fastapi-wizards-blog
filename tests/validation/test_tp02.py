"""TP 2 : premiers endpoints.

docker compose exec app uv run pytest tests/validation/test_tp02.py
"""


def test_accueil(client):
    response = client.get("/")
    assert response.status_code == 200, (
        "GET / doit répondre 200 : la route est-elle déclarée ?"
    )
    assert response.json() == {"message": "Le blog des Wizards"}, (
        'GET / doit renvoyer exactement {"message": "Le blog des Wizards"}.'
    )


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200, (
        "GET /health doit répondre 200 : la route est-elle déclarée ?"
    )
    assert response.json() == {"status": "ok"}, (
        'GET /health doit renvoyer {"status": "ok"}.'
    )


def test_titre_de_l_api(client):
    titre = client.get("/openapi.json").json()["info"]["title"]
    assert titre == "Blog des Wizards", (
        f'Le titre affiché dans /docs est « {titre} » : passez title="Blog des Wizards" à FastAPI().'
    )


def test_routes_documentees(client):
    paths = client.get("/openapi.json").json()["paths"]
    for route in ("/", "/health"):
        assert "get" in paths.get(route, {}), f"GET {route} doit apparaître dans /docs."
