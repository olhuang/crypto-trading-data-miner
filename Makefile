COMPOSE ?= docker compose
DB_CONTAINER ?= crypto_trading_postgres
DB_USER ?= postgres
DB_NAME ?= crypto_trading

.PHONY: up down logs reset-db psql verify-phase1

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

reset-db:
	$(COMPOSE) down -v
	$(COMPOSE) up -d

psql:
	docker exec -it $(DB_CONTAINER) psql -U $(DB_USER) -d $(DB_NAME)

verify-phase1:
	docker exec -i $(DB_CONTAINER) psql -U $(DB_USER) -d $(DB_NAME) -f /docker-entrypoint-initdb.d/../verify/phase_1_verification.sql
