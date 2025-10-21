# Makefile per lo stack Data Engineering (compatibile con make 3.81)
COMPOSE = docker compose -f compose/docker-compose.yml

.PHONY: help up down restart ps logs build-elt etl psql sql refresh clean

help:
	@echo ""
	@echo "Comandi disponibili:"
	@echo "  make up           - Avvia Postgres + Grafana"
	@echo "  make down         - Ferma e rimuove i container"
	@echo "  make restart      - Riavvia i servizi"
	@echo "  make ps           - Stato dei servizi"
	@echo "  make logs         - Log tail -100 (Ctrl+C per uscire)"
	@echo "  make build-elt    - Build dell'immagine del job ETL"
	@echo "  make etl          - Esegue il job ETL (container effimero)"
	@echo "  make psql         - Apre la shell psql"
	@echo "  make sql Q=\"...\" - Esegue una query one-shot su Postgres"
	@echo "  make refresh      - up -> etl -> ps"
	@echo "  make clean        - Spegne tutto e pulisce volumi orfani"
	@echo ""

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

# Build esplicito dell'immagine del job (utile se cambi docker/Dockerfile.elt)
build-elt:
	$(COMPOSE) build elt

# Esegue il job ETL in un container effimero
etl:
	$(COMPOSE) run --rm elt

# psql interattivo
psql:
	$(COMPOSE) exec -e PGPASSWORD=analytics postgres psql -U analytics -d analytics

# Query one-shot: make sql Q="SELECT COUNT(*) FROM public.brand_stats;"
sql:
	$(COMPOSE) exec -T -e PGPASSWORD=analytics postgres psql -U analytics -d analytics -c "$(Q)"

# Avvio stack + ETL + stato
refresh: up etl ps

# Spegne lo stack e pulisce volumi orfani (non rimuove i tuoi file locali)
clean:
	$(COMPOSE) down -v
	docker volume prune -f
