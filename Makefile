.PHONY: docker-build docker-test docker-up docker-down docker-ui docker-isolated-test

docker-build:
	docker compose build

docker-test:
	docker compose run --rm app pytest
	docker compose run --rm app python scripts/docker_e2e.py --config config.docker.json

docker-up:
	docker compose up -d node-a node-b node-c

docker-down:
	docker compose down

docker-ui:
	docker compose up ui

docker-isolated-test:
	docker compose -f docker-compose.isolated.yml up -d node-a node-b node-c
	docker compose -f docker-compose.isolated.yml run --rm app python scripts/docker_network_probe.py --config config.docker.json --node A --expect-failure
	docker compose -f docker-compose.isolated.yml down
