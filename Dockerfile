FROM python:3.13-slim

WORKDIR /usr/src/app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specs and lockfile
COPY pyproject.toml uv.lock ./

# Install dependencies from lockfile
RUN uv sync --frozen --no-dev --no-cache

# Copy the app source
COPY . .

CMD [ "uv", "run", "python", "./run.py" ]