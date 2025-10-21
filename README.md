# Data Engineering - Quickstart & Guida

> **Nota sui path con spazi (macOS):** quando usi il terminale, **metti tra virgolette** il path della cartella progetto:  
> `cd "/Users/<utente>/Data Engineering"`

## Concetti chiave (in 2 minuti)

- **Docker**: avvia servizi isolati in **container** (es. Postgres, Grafana).  
- **Docker Compose**: accende più servizi assieme (definiti in `compose/docker-compose.yml`).
- **ELT**: **E**xtract (legge CSV) → **L**oad/**T**ransform (calcola metriche) → scrive su **Postgres**.
- **SQL**: linguaggio (SELECT/INSERT/…) capito dai motori DB (PostgreSQL nel nostro caso).
- **Grafana**: client BI che si collega a Postgres e **visualizza** le query in grafici/KPI.
- **Makefile**: comandi corti (es. `make up`) che eseguono comandi lunghi Docker/psql per te.

## Prerequisiti

- **Docker Desktop** installato e in esecuzione.
- **make** disponibile (su macOS è già presente con Xcode Command Line Tools).
- (Facoltativo) **VS Code** per comodità.

## Installazione e avvio rapido (Quickstart)

1. **Clona** il repository:
   ```bash
   git clone https://github.com/<tuo-utente>/<tuo-repo>.git
   cd "<tuo-repo>"   # o cd "/Users/<te>/Data Engineering"
   ```

2. **Metti/aggiorna il CSV sorgente**
   ```bash
   # Sostituisci con il path del tuo file locale
   cp "/percorso/del/tuo/auto_dati.csv" "data/raw/auto_dati.csv"
   ```
   - Il job si aspetta almeno le colonne: marca, versione, prezzo.
   - (Opzionale) capacita_batteria_kwh se vuoi la metrica batteria media.

3. **Accendi Postgres + Grafana**

   ```bash
   make up
   ```

   Verifica che siano su:
   ```bash
   docker compose -f compose/docker-compose.yml ps
   # atteso:
   # de-postgres ... healthy
   # de-grafana ... Up (0.0.0.0:3000->3000/tcp)
   ```

4. **Esegui l’ELT (carica/aggrega nel DB analytics)**

   ```bash
   make etl
   ```

   Output atteso:
   
   DONE → gold brand_stats → Postgres (public.brand_stats)

5. **Apri Grafana (prima volta: crea il datasource Postgres)**

   Apri [http://localhost:3000](http://localhost:3000)

   - Login: admin / admin (se richiesto).
   - Vai su: Connections → Data sources → Add data source → PostgreSQL
   - Host: postgres:5432
   - Database: analytics
   - User: analytics
   - Password: analytics
   - SSL mode: disable
   - Save & test (deve dare “Database Connection OK”)

   Se hai già fatto questa configurazione in passato e non hai cancellato la cartella grafana/, puoi saltare questo punto.

6. **Importa la dashboard (JSON già pronto)**
   - In Grafana: Dashboards → New → Import → Upload JSON file
   - Seleziona: grafana/dashboards/Auto Scraping Dashboard.json
   - Alla voce data source scegli quello creato al punto 5
   - Clicca Import

7. **Usa la dashboard**
   - Variabili in alto: marca (multi-select con “All”), topn (5/10/15/20/30).
   - Pannelli:
     - Versioni totali (KPI),
     - Prezzo medio (bar chart),
     - Differenziali min/medio/max per marca (bar chart),
     - Tabulato con tutte le metriche per marca (tabella).

8. **Spegni tutto quando hai finito**

   ```bash
   make down
   ```
