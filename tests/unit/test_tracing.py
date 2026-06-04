from unittest.mock import MagicMock, patch

from app.core.tracing import setup_tracing


def test_setup_tracing() -> None:
    mock_app = MagicMock()
    mock_engine = MagicMock()

    with (
        patch("opentelemetry.trace.set_tracer_provider") as mock_set_provider,
        patch(
            "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"
        ) as mock_fastapi_inst,
        patch(
            "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor.instrument"
        ) as mock_sqla_inst,
        patch(
            "opentelemetry.instrumentation.redis.RedisInstrumentor.instrument"
        ) as mock_redis_inst,
        patch(
            "opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor.instrument"
        ) as mock_httpx_inst,
    ):
        setup_tracing(mock_app, mock_engine)
        mock_set_provider.assert_called_once()
        mock_fastapi_inst.assert_called_once_with(mock_app)
        mock_sqla_inst.assert_called_once_with(engine=mock_engine.sync_engine)
        mock_redis_inst.assert_called_once()
        mock_httpx_inst.assert_called_once()
