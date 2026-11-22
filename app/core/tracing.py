from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings


def setup_tracing(app: FastAPI, engine: AsyncEngine) -> None:
    provider = TracerProvider()
    if settings.TRACING_CONSOLE:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
