# syntax=docker/dockerfile:1
#
# SmolRank production image: Django + Gunicorn + WhiteNoise, using a multi-stage build.
#
# WHAT IS A MULTI-STAGE BUILD?
#   We build in two "stages". Stage 1 (builder) installs the Python packages. Stage 2 (runtime)
#   starts from a fresh, clean image and copies only the finished result out of stage 1.
#   Everything used only for building is thrown away, so the final image stays small.
#
# BUILD:  docker build -t smolrank .
# RUN:    see docker-compose.yml (it also starts the PostgreSQL database for you)


# ───────────────────────────── Stage 1: builder ─────────────────────────────
# "slim" = a small Debian-based Python image (much smaller than the full one).
FROM python:3.12-slim AS builder

# Don't keep pip's download cache and don't nag about pip upgrades (saves space and noise).
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install packages into a virtual environment at /opt/venv. A venv is one folder holding
# everything, which makes it easy to copy into the next stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ONLY requirements.txt first. Docker caches each step, so as long as this file doesn't
# change, rebuilds skip the slow "pip install" and only redo the steps after it.
COPY requirements.txt .
RUN pip install -r requirements.txt


# ───────────────────────────── Stage 2: runtime ─────────────────────────────
# A brand-new clean image. Nothing from stage 1 is here unless we copy it in below.
FROM python:3.12-slim AS runtime

# PYTHONDONTWRITEBYTECODE: don't create .pyc files (not needed in a container).
# PYTHONUNBUFFERED:        send logs straight to the console so `docker logs` shows them live.
# PATH:                    use the packages we copied from the builder stage.
# DJANGO_SETTINGS_MODULE:  use the production settings (HTTPS-only cookies, requires a real secret key
#                          and a DATABASE_URL, and so on).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# Security: don't run the app as root. Create a normal user called "app" instead.
RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app

WORKDIR /app

# Copy the installed packages from stage 1 (this is the only thing we take from it).
COPY --from=builder /opt/venv /opt/venv

# Copy the project code. Files listed in .dockerignore (like .env and venv/) are NOT copied.
COPY --chown=app:app . .

# Collect all static files (CSS/JS, including the admin's) into /app/staticfiles at BUILD time.
# WhiteNoise then serves them straight from the container, so no separate web server is needed.
#
# Django's production settings refuse to start without a secret key and a database URL, so we give
# throwaway values for THIS ONE COMMAND only. They are not saved as environment variables in the
# image and collectstatic never connects to a database. Real values come in when the container runs.
RUN DJANGO_SECRET_KEY="build-only-throwaway-key-0123456789-0123456789-0123456789-abcdef" \
    DATABASE_URL="postgresql://build:build@localhost:5432/build" \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles

# From here on, everything (including the running app) uses the non-root user.
USER app

# Tell Docker (and people reading this) that the app listens on port 8000 inside the container.
# EXPOSE is documentation; the port is actually published in docker-compose.yml.
EXPOSE 8000

# Start Gunicorn, the production web server for Django.
#   config.wsgi:application  -> where Django's WSGI app lives
#   --bind 0.0.0.0:8000      -> listen on all interfaces (PORT can override it, hosts like Railway set it)
#   --workers                -> how many requests are handled in parallel (GUNICORN_WORKERS, default 3)
#   --access-logfile -       -> print access logs to the console
# "sh -c" is used so the ${...} variables above are filled in when the container starts.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${GUNICORN_WORKERS:-3} --access-logfile -"]
