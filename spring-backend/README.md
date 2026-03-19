# Spring Backend (3-Stage Java Migration)

This module implements the migration plan tasks:

- Stage 1: Spring Boot API facade with Python engine bridge.
- Stage 2: Contract freeze + parity harness + JPA/Flyway baseline.
- Stage 3: Java engine skeleton (`java-engine` profile).

## Run

```bash
cd spring-backend
./gradlew bootRun
```

Environment:

- `PY_ENGINE_BASE_URL` (default `http://127.0.0.1:8000`)
- `SPRING_DATASOURCE_URL` / `SPRING_DATASOURCE_USERNAME` / `SPRING_DATASOURCE_PASSWORD`

## Parity Check

```bash
python3 scripts/parity_harness.py --py http://127.0.0.1:8000 --spring http://127.0.0.1:8080 --steps 30
```
