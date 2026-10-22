from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

from app.templating import templates

MESSAGES = {
    "string_too_short": "{min_length} caractères minimum.",
    "string_too_long": "{max_length} caractères maximum.",
    "missing": "Ce champ est obligatoire.",
}


def messages_par_champ(exc: RequestValidationError) -> dict[str, str]:
    """Un message en français par champ du formulaire."""
    erreurs = {}
    for erreur in exc.errors():
        modele = MESSAGES.get(erreur["type"], erreur["msg"])
        erreurs[str(erreur["loc"][-1])] = modele.format(**erreur.get("ctx", {}))
    return erreurs


async def validation_handler(request: Request, exc: RequestValidationError):
    """Réaffiche le formulaire en erreur ; l'API garde son 422 en JSON."""
    formulaire = request.app.url_path_for("create_article_form")
    if request.method == "POST" and request.url.path == formulaire:
        return templates.TemplateResponse(
            request,
            "articles/new.html",
            {
                "erreurs": messages_par_champ(exc),
                "valeurs": dict(await request.form()),
            },
            status_code=422,
        )
    return await request_validation_exception_handler(request, exc)
