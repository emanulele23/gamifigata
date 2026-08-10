.PHONY: setup onboard up down logs health test build discover checkin

setup:
	chmod +x scripts/*.sh scripts/*.py
	./scripts/setup.sh

onboard:
	python3 scripts/onboard.py

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

health:
	curl -sS http://localhost:5000/health | python3 -m json.tool

checkin:
	curl -sS -X POST http://localhost:5000/checkin \
	  -H 'Content-Type: application/json' \
	  -d '{"send": true, "try_call": true}' | python3 -m json.tool

discover:
	curl -sS http://localhost:5000/telegram/discover-chat | python3 -m json.tool

test:
	cd echo-api && PYTHONPATH=. python3 -m app.test_parsing_db

build:
	docker compose build
