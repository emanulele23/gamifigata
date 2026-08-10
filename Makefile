.PHONY: setup up down logs health test build discover

setup:
	chmod +x scripts/*.sh scripts/*.py
	./scripts/setup.sh

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

health:
	curl -sS http://localhost:5000/health | python3 -m json.tool

discover:
	curl -sS http://localhost:5000/telegram/discover-chat | python3 -m json.tool

test:
	cd echo-api && PYTHONPATH=. python3 -m app.test_parsing_db

build:
	docker compose build
