# PostgreSQL backup and restore

This runbook uses manual logical backups. Recovery stops at the snapshot in the most recent successful dump you still have. Any writes committed after that snapshot would be lost. The project ships without an automated backup schedule or WAL archiving, so there is no guaranteed recovery point objective. The drill verifies a disposable database restore. Production recovery time is unknown.

Store real backups off-host with restricted access and encryption. The custom archive contains application data, including account records. Restore into a fresh database and verify it before redirecting the application. The restore flags omit ownership and grants, so provision the runtime and migration roles and their grants separately. Redis cache and queued mail are outside this PostgreSQL backup.

## Disposable drill

From the repository root, populate the disposable PostgreSQL 16 database with the integration test fixtures using `COMPOSE_DISABLE_ENV_FILE=1 make test`. Let the suite finish before comparing source and restore counts.

```sh
set -eu
export COMPOSE_DISABLE_ENV_FILE=1
restore_compose() {
  docker compose -p spendwise-test -f docker-compose.test.yml "$@"
}

umask 077
dump_dir=$(mktemp -d /tmp/spendwise-restore.XXXXXX)
dump="$dump_dir/spendwise.dump"
restore_db="spendwise_restore_$(date -u +%Y%m%d%H%M%S)"
printf 'Archive directory %s\nRestore database %s\n' "$dump_dir" "$restore_db"

restore_compose exec -T postgres pg_dump --version
restore_compose exec -T postgres pg_dump \
  --username=spendwise_test --dbname=spendwise_test --format=custom > "$dump"
printf 'pg_dump exit 0\n'
test -s "$dump"

restore_compose exec -T postgres createdb \
  --username=spendwise_test --template=template0 "$restore_db"
restore_compose exec -T postgres pg_restore \
  --username=spendwise_test --dbname="$restore_db" \
  --no-owner --no-privileges --single-transaction --exit-on-error < "$dump"
printf 'pg_restore exit 0\n'

counts="SELECT 'alembic_version', version_num FROM alembic_version
UNION ALL SELECT 'audit_logs', count(*)::text FROM audit_logs
UNION ALL SELECT 'categories', count(*)::text FROM categories
UNION ALL SELECT 'oauth_accounts', count(*)::text FROM oauth_accounts
UNION ALL SELECT 'refresh_tokens', count(*)::text FROM refresh_tokens
UNION ALL SELECT 'transactions', count(*)::text FROM transactions
UNION ALL SELECT 'users', count(*)::text FROM users
ORDER BY 1"
for database in spendwise_test "$restore_db"; do
  restore_compose exec -T postgres psql -XAt --set=ON_ERROR_STOP=1 \
    --username=spendwise_test --dbname="$database" --command="$counts" > "$dump_dir/$database.txt"
done
printf 'Source and restored database comparison\n'
diff -u "$dump_dir/spendwise_test.txt" "$dump_dir/$restore_db.txt"
cat "$dump_dir/$restore_db.txt"
printf 'diff exit 0\n'
```

Output from 2026-11-24 UTC. Counts depend on the data present when you take the dump.

```text
Archive directory /tmp/spendwise-restore.rZLyEk
Restore database spendwise_restore_20261124060936
pg_dump (PostgreSQL) 16.16
pg_dump exit 0
pg_restore exit 0
Source and restored database comparison
alembic_version|a8b7e2d1c690
audit_logs|9
categories|1
oauth_accounts|0
refresh_tokens|4
transactions|1
users|5
diff exit 0
```

The recovery point for this drill was the test database snapshot taken at approximately 06:09 UTC. The comparison verified the Alembic revision and row counts across all application tables.

[PostgreSQL 16 pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html) · [PostgreSQL 16 pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)
