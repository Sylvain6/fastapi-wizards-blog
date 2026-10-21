FROM ghcr.io/astral-sh/uv:0.13-python3.13-trixie-slim

ENV UV_LINK_MODE=copy

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que uv.lock ne change pas
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

EXPOSE 80

CMD ["uv", "run", "fastapi", "dev", "--host", "0.0.0.0", "--port", "80"]
