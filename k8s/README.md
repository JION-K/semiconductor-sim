# Kubernetes: Spring DB 연결

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
