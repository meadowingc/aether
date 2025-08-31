dev:
	uv run manage.py runserver 

migrate:
	uv run manage.py migrate

makemigrations:
	uv run manage.py makemigrations

check:
	uv run manage.py check

shell:
	uv run manage.py shell

create-admin:
	uv run manage.py createsuperuser

serve:
	DJANGO_PROD=True uv run gunicorn aether.wsgi --bind "127.0.0.1:4287"