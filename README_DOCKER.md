# Semi Fab Sim - Docker 실행 가이드

## 1) 최초 1회: DB 스키마/데이터 적재

```bash
docker compose --profile init up init-db
```

- `init_db.py`가 실행되며, 테이블 생성 + 엑셀 데이터 적재를 수행합니다.
- 이 단계는 필요할 때만 다시 실행하면 됩니다.

## 2) Spring 전환 기본 실행 (권장)

```bash
docker compose up -d
```

- Python API(엔진): `http://127.0.0.1:8000`
- Spring API(프론트 연결 대상): `http://127.0.0.1:8080`
- Frontend: `http://127.0.0.1:5173`
- Frontend는 `.env`의 `VITE_API_URL=http://127.0.0.1:8080` 기준으로 Spring에 연결됩니다.

## 3) 중지

```bash
docker compose down
```

## 4) 볼륨까지 완전 초기화 (DB 데이터 삭제)

```bash
docker compose down -v
```

그 후 다시 데이터 적재:

```bash
docker compose --profile init up init-db
```
