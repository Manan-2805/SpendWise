from unittest.mock import MagicMock, patch

from app.core.logging import (
    configure_logging,
    inject_otel_to_logs,
    redact_secrets_processor,
)


def test_redact_secrets_processor() -> None:
    event_dict = {
        "event": "login_attempt",
        "password": "my_secret_password",
        "nested": {
            "credit_card": "1234-5678-9012-3456",
            "email": "test@example.com",
            "list": ["another_email@domain.com", {"cvv": "123"}],
        },
    }
    redacted = redact_secrets_processor(None, "info", event_dict)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["credit_card"] == "[REDACTED]"
    assert redacted["nested"]["email"] == "[REDACTED_EMAIL]"
    assert redacted["nested"]["list"][0] == "[REDACTED_EMAIL]"
    assert redacted["nested"]["list"][1]["cvv"] == "[REDACTED]"


def test_inject_otel_to_logs_no_span() -> None:
    event_dict = {"event": "no_span"}
    res = inject_otel_to_logs(None, "info", event_dict)
    assert "trace_id" not in res


def test_inject_otel_to_logs_with_span() -> None:
    mock_span = MagicMock()
    mock_span.get_span_context().is_valid = True
    mock_span.get_span_context().trace_id = 12345678901234567890123456789012
    mock_span.get_span_context().span_id = 1234567890123456

    with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
        event_dict = {"event": "with_span"}
        res = inject_otel_to_logs(None, "info", event_dict)
        assert "trace_id" in res
        assert "span_id" in res


def test_configure_logging() -> None:
    # Test both debug=True and debug=False
    configure_logging(debug=True)
    configure_logging(debug=False)


def test_production_logging_preserves_json_renderer() -> None:
    import structlog

    configure_logging(debug=False)

    assert isinstance(
        structlog.get_config()["processors"][-1], structlog.processors.JSONRenderer
    )
