"""Create settings for a fresh development checkout."""

import os
import secrets
from pathlib import Path


def write_settings(path: Path, contents: str) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as config:
            config.write(contents)
    except FileExistsError:
        return


def setup_monitoring() -> None:
    write_settings(
        Path(".env.monitoring"), f"GRAFANA_ADMIN_PASSWORD={secrets.token_hex(32)}\n"
    )


def main() -> None:
    write_settings(
        Path(".env"),
        "ENVIRONMENT=development\n"
        "DEBUG=true\n"
        "DATABASE_URL=postgresql://spendwise:spendwise_dev_password@127.0.0.1:15432/spendwise\n"
        "REDIS_URL=redis://127.0.0.1:16379/0\n"
        "CELERY_BROKER_URL=redis://127.0.0.1:16379/1\n"
        "CELERY_RESULT_BACKEND=redis://127.0.0.1:16379/2\n"
        f"SECRET_KEY={secrets.token_hex(32)}\n",
    )
    setup_monitoring()


if __name__ == "__main__":
    main()
