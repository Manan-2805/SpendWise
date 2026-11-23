# API capacity

## Admission-limit sweep · 2026-11-23

Each candidate ran one 60-second round at 240 req/s, then one at 640 req/s. Each pair started with its own verified disposable fixture of 5,000 users, 20,000 categories, and 320,000 transactions. The open-loop mix was 87% reads and reports (44% transaction lists and 43% monthly summaries), 12% transaction writes, and 1% logins. Two Granian workers and two Celery worker processes ran on the four-logical-CPU WSL2 host. The harness probed liveness and readiness once per second.

| Slots per worker | Offered req/s | Successful req/s | Issued | Overall p95 | `503` p95 | `503`s with `Retry-After` | Liveness | Readiness | Generator CPU |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 240 | 202.48 | 100% | 87.83 ms | 80.03 ms | 2,251 / 2,251 | 100% | 100% | 31.70% |
| 8 | 640 | 166.57 | 100% | 159.88 ms | 138.90 ms | 28,406 / 28,406 | 100% | 100% | 67.08% |
| 16 | 240 | 235.33 | 100% | 127.43 ms | 156.79 ms | 280 / 280 | 100% | 100% | 32.27% |
| 16 | 640 | 198.02 | 99.98% | 221.71 ms | 153.90 ms | 26,513 / 26,513 | 100% | 100% | 68.68% |
| 32 | 240 | 235.98 | 100% | 204.23 ms | 317.20 ms | 241 / 241 | 100% | 100% | 32.62% |
| 32 | 640 | 162.87 | 93.90% | 1,340.26 ms | 1,182.55 ms | 26,285 / 26,285 | 100% | 98.33% | 84.98% |

The default is **16 in-flight requests per API worker**. It delivered the highest 640 req/s goodput among candidates that reached at least 98% readiness at 240 req/s and met the 200 ms rejection p95 target at 640 req/s. Both the 8- and 16-slot candidates sustained at least 160 successful req/s and 100% liveness in the high-load round.

Generator CPU is the mean percentage of one logical core. At 640 req/s with 16 slots, the generator issued 38,394 of 38,400 requests. It met the issuance target at 68.68% of one core. At 32 slots it issued 36,057 of 38,400, so that measurement is issuance-limited. The cause of the issuance shortfall is unresolved. The p95 values are measured from scheduled request time. The full before-and-after runs and recovery measurements are specified in the [overload plan](plans/2026-11-23-overload.md).

Earlier local trials left synthetic `capacity_user_*` accounts, their categories, and benchmark transactions in the default development database. Those rows remain in place. `make seed-capacity` and `make capacity` validate the dedicated disposable database before migrations, seed inserts, or workload writes.
