from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.init_db import create_tables, drop_tables, seed_default_categories


async def test_init_db_functions() -> None:
    # Test create_tables
    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.__aenter__.return_value = mock_conn
    mock_engine.begin.return_value = mock_conn
    with patch("app.db.init_db.engine", mock_engine):
        await create_tables()
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()

    # Test drop_tables
    mock_engine_drop = MagicMock()
    mock_conn_drop = AsyncMock()
    mock_conn_drop.__aenter__.return_value = mock_conn_drop
    mock_engine_drop.begin.return_value = mock_conn_drop
    with patch("app.db.init_db.engine", mock_engine_drop):
        await drop_tables()
        mock_engine_drop.begin.assert_called_once()
        mock_conn_drop.run_sync.assert_called_once()

    # Test seed_default_categories
    mock_session = AsyncMock(spec=AsyncSession)
    await seed_default_categories(mock_session, user_id=1)
    assert mock_session.add.call_count == 10
    mock_session.flush.assert_called_once()
