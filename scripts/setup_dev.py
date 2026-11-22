"""Create settings for a fresh development checkout."""

import os
import secrets
from pathlib import Path


def main() -> None:
    try:
        fd = os.open(Path(".env"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as config:
            config.write(
                "ENVIRONMENT=development\n"
                "DEBUG=true\n"
                "DATABASE_URL=postgresql://spendwise:spendwise_dev_password@127.0.0.1:15432/spendwise\n"
                "REDIS_URL=redis://127.0.0.1:16379/0\n"
                "CELERY_BROKER_URL=redis://127.0.0.1:16379/1\n"
                "CELERY_RESULT_BACKEND=redis://127.0.0.1:16379/2\n"
                f"SECRET_KEY={secrets.token_hex(32)}\n"
            )
    except FileExistsError:
        return


if __name__ == "__main__":
    main()
