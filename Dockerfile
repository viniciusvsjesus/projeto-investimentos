# syntax=docker/dockerfile:1
#
# Imagem da API. Multi-stage por decisão da ADR-008: o estágio de build carrega
# compilador e cache do pip; a imagem final não leva nada disso.

# ---------------------------------------------------------------- builder ---
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PATH="/opt/venv/bin:$PATH"

# Artigo VI: usuário sem privilégio. Um escape de processo dentro do container
# não deve herdar root.
RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home --home-dir /home/appuser appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pyproject.toml ./

USER appuser

EXPOSE 8000

# Healthcheck em Python puro: instalar curl só para isso aumentaria a imagem e
# a superfície de ataque sem necessidade (ADR-008).
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "investimentos.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ------------------------------------------------------------------- dev ----
# Estágio usado pelo perfil de desenvolvimento do compose: acrescenta as
# ferramentas de teste sem pesar na imagem de produção.
FROM runtime AS dev

USER root
# Os dois arquivos: requirements-dev.txt começa com '-r requirements.txt'.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
COPY --chown=appuser:appuser tests/ ./tests/
COPY --chown=appuser:appuser specs/ ./specs/
USER appuser

CMD ["uvicorn", "investimentos.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]
