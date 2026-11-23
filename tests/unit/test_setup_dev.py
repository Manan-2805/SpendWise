import os
from hashlib import sha256
from pathlib import Path

import pytest

from scripts import setup_dev


def test_monitoring_settings_are_private_and_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = Path(".env.monitoring")

    setup_dev.setup_monitoring()

    setting, value = path.read_text(encoding="utf-8").strip().split("=", 1)
    assert setting == "GRAFANA_ADMIN_PASSWORD"
    has_expected_length = len(value) == 64
    assert has_expected_length
    assert os.stat(path).st_mode & 0o777 == 0o600
    original = sha256(path.read_bytes()).digest()

    setup_dev.setup_monitoring()

    assert sha256(path.read_bytes()).digest() == original
