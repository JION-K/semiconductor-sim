# Kubernetes: Spring DB 연결

## 과제용: 클러스터 안에 Postgres 빠르게 올리기

RDS 없이 **EKS 안에만** DB를 두고 맞추려면:

1. **네임스페이스** (이미 CD에서 쓰는 경우 생략 가능)
   ```bash
   kubectl create namespace skala3-ai1 --dry-run=client -o yaml | kubectl apply -f -
   ```

2. **`k8s/postgres-in-cluster.yaml` 수정**  
   - `postgres-app-secret`의 `postgres-password`를 원하는 값으로 변경 (기본 `postgres`는 데모용).

3. **Postgres 배포**
   ```bash
   kubectl apply -f k8s/postgres-in-cluster.yaml
   kubectl wait --for=condition=ready pod -l app=postgres -n skala3-ai1 --timeout=120s
   kubectl get pods,svc -n skala3-ai1 -l app=postgres
   ```

4. **GitHub Actions Secrets** (또는 수동 `semi-fab-db`) — **Postgres와 동일한 비밀번호**로 맞춤
   - `DB_JDBC_URL` = `jdbc:postgresql://postgres.skala3-ai1.svc.cluster.local:5432/postgres`
   - `DB_USERNAME` = `postgres`
   - `DB_PASSWORD` = 위에서 넣은 비밀번호

5. **CI/CD 다시 실행**하거나, 수동으로:
   ```bash
   kubectl create secret generic semi-fab-db -n skala3-ai1 \
     --from-literal=jdbc-url='jdbc:postgresql://postgres.skala3-ai1.svc.cluster.local:5432/postgres' \
     --from-literal=username='postgres' \
     --from-literal=password='여기비밀번호' \
     --dry-run=client -o yaml | kubectl apply -f -
   kubectl rollout restart deployment/deploy-sk008-app -n skala3-ai1
   ```

**주의:** 이 매니페스트는 **emptyDir**라 Pod가 지워지면 DB 데이터도 사라집니다. 과제/데모용입니다. 운영이면 RDS 또는 StatefulSet+PVC를 쓰세요.

---

`application.yml`은 다음 환경 변수를 읽습니다.

| 환경 변수 | 매핑 |
|-----------|------|
| `SPRING_DATASOURCE_URL` | `spring.datasource.url` |
| `SPRING_DATASOURCE_USERNAME` | `spring.datasource.username` |
| `SPRING_DATASOURCE_PASSWORD` | `spring.datasource.password` |
| `SPRING_PORT` | `server.port` (기본 8080) |
| `ENGINE_MODE` | `engine.mode` (기본 `java`) |

## 적용 순서

1. 클러스터에 PostgreSQL이 있는지 정합니다 (클러스터 내부 Service, RDS 등).
2. JDBC URL을 만듭니다. 클러스터 내부 예: `jdbc:postgresql://<서비스이름>.<네임스페이스>.svc.cluster.local:5432/<DB이름>`
3. `semi-fab-db-secret.example.yaml`을 복사해 값을 채우고 Secret 이름/namespace를 Deployment와 맞춥니다.
4. Secret 적용: `kubectl apply -f <수정한-secret.yaml>`
5. 루트 `deployment.yaml`의 `secretKeyRef.name`이 Secret 이름과 같은지 확인한 뒤 배포합니다.

## 확인

- `kubectl logs -n skala3-ai1 deploy/deploy-sk008-app` 에서 Flyway/Hikari 기동 여부 확인
- `kubectl describe pod -n skala3-ai1 -l app=spring-backend-sk008` 에서 env 주입 확인

`hibernate.dialect`만 넣는 것은 JDBC URL이 없으면 근본 해결이 되지 않습니다.
