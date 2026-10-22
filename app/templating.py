from fastapi import Request
from fastapi.templating import Jinja2Templates


def etat_de_connexion(request: Request) -> dict[str, bool]:
    """Ajoute « connecte » au contexte de chaque page, pour le menu."""
    return {"connecte": "access_token" in request.cookies}


templates = Jinja2Templates(
    directory="app/templates", context_processors=[etat_de_connexion]
)
