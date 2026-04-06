.PHONY: install run shell migrate makemigrations createsuperuser \
        docker-up docker-down docker-logs \
        celery-worker celery-beat

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

run:
	python manage.py runserver 0.0.0.0:8502

shell:
	python manage.py shell

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

createsuperuser:
	python manage.py createsuperuser

collectstatic:
	python manage.py collectstatic --noinput

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app

celery-worker:
	celery -A config worker --concurrency=5 -Q evaluation,maintenance -l info

celery-beat:
	celery -A config beat -l info
