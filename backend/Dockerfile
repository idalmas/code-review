FROM python:3.13-slim

RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER nobody
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
