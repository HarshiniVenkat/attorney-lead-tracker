FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency layer is cached separately from source so code edits don't reinstall.
COPY pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e ".[dev]"

COPY . .

# Resume files land here when STORAGE_BACKEND=local.
RUN mkdir -p /var/lib/alma/resumes

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
