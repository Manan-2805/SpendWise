from collections import Counter
from datetime import date
from signal import SIGKILL
from unittest.mock import patch

from app.schemas.transaction import TransactionCreate
from scripts import run_capacity_test


def test_operation_order_has_the_requested_mix_and_is_repeatable() -> None:
    first = run_capacity_test.operation_order()
    assert first == run_capacity_test.operation_order()
    assert Counter(first) == {
        "transactions": 44,
        "report": 43,
        "write": 12,
        "login": 1,
    }


def test_capacity_write_matches_the_transaction_schema() -> None:
    today = date(2026, 11, 23)
    transaction = TransactionCreate.model_validate(
        run_capacity_test.transaction_payload(7, today)
    )
    assert transaction.category_id == 7
    assert transaction.transaction_date == today


def test_container_cpu_handles_docker_screen_updates() -> None:
    output = "\x1b[2J\x1b[Hstack-postgres-1 10.00%\n\x1b[Hstack-postgres-1 30.00%\n"
    assert run_capacity_test.container_cpu(output) == {
        "stack-postgres-1": {"mean": 20.0, "peak": 30.0}
    }


def test_process_cleans_up_workers_after_the_parent_exits() -> None:
    with (
        patch.object(run_capacity_test.subprocess, "Popen") as popen,
        patch.object(run_capacity_test.os, "killpg") as kill_group,
    ):
        child = popen.return_value.__enter__.return_value
        child.pid = 123
        child.poll.return_value = 0
        with run_capacity_test.process(["granian"], {}):
            pass

    assert popen.call_args.kwargs["start_new_session"] is True
    kill_group.assert_called_once_with(123, SIGKILL)
