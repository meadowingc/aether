SHELL := /usr/bin/env bash
.SHELLFLAGS := -o pipefail -c

.PHONY: dev migrate format makemigrations check shell create-admin collectstatic serve

dev:
    uv run manage.py runserver

migrate:
    uv run manage.py migrate

format:
    @git ls-files -z -- '*.html' | xargs -0r uv run djade

makemigrations:
    uv run manage.py makemigrations

check:
    uv run manage.py check

shell:
    uv run manage.py shell

create-admin:
    uv run manage.py createsuperuser

collectstatic:
    uv run manage.py collectstatic --noinput --clear

pull:
  git pull

serve: pull migrate collectstatic
    DJANGO_PROD=True gunicorn aether.wsgi -c gunicorn_config.py
