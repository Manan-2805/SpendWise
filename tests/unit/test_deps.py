from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import (
    get_current_active_user,
    get_current_user,
    get_current_verified_user,
    get_db,
)
from app.core.exceptions import (
    AuthenticationError,
    InactiveUserError,
    UnverifiedEmailError,
)
from app.models.user import User


@pytest.mark.asyncio
async def test_get_db_success() -> None:
    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    mock_cm.__aexit__.return_value = False
    mock_session_local = MagicMock(return_value=mock_cm)
    with patch("app.api.deps.AsyncSessionLocal", mock_session_local):
        generator = get_db()
        db = await anext(generator)
        assert db == mock_session
        with suppress(StopAsyncIteration):
            await anext(generator)

        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_db_exception() -> None:
    mock_session = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_session
    mock_cm.__aexit__.return_value = False
    mock_session_local = MagicMock(return_value=mock_cm)
    with patch("app.api.deps.AsyncSessionLocal", mock_session_local):
        generator = get_db()
        await anext(generator)
        with pytest.raises(ValueError):
            await generator.athrow(ValueError("test"))
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_user_no_token() -> None:
    request = MagicMock()
    request.cookies = {}
    with pytest.raises(AuthenticationError):
        await get_current_user(request, token_from_header=None, db=MagicMock())


@pytest.mark.asyncio
async def test_get_current_user_missing_sub() -> None:
    request = MagicMock()
    request.cookies = {"access_token": "token"}
    with (
        patch("app.api.deps.verify_token", return_value={}),
        pytest.raises(AuthenticationError),
    ):
        await get_current_user(request, token_from_header=None, db=MagicMock())


@pytest.mark.asyncio
async def test_get_current_user_invalid_token() -> None:
    request = MagicMock()
    request.cookies = {"access_token": "token"}
    with (
        patch("app.api.deps.verify_token", side_effect=Exception),
        pytest.raises(AuthenticationError),
    ):
        await get_current_user(request, token_from_header=None, db=MagicMock())


@pytest.mark.asyncio
async def test_get_current_user_not_found() -> None:
    request = MagicMock()
    request.cookies = {"access_token": "token"}
    mock_db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result
    with (
        patch("app.api.deps.verify_token", return_value={"sub": 1}),
        pytest.raises(AuthenticationError),
    ):
        await get_current_user(request, token_from_header=None, db=mock_db)


@pytest.mark.asyncio
async def test_get_current_user_success() -> None:
    request = MagicMock()
    request.cookies = {}
    mock_db = AsyncMock()
    mock_user = User(id=1, is_active=True)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = execute_result
    with patch("app.api.deps.verify_token", return_value={"sub": 1}):
        res = await get_current_user(request, token_from_header="token", db=mock_db)
        assert res == mock_user
        assert request.state.user == mock_user


@pytest.mark.asyncio
async def test_get_current_active_user_inactive() -> None:
    mock_user = User(id=1, is_active=False)
    with pytest.raises(InactiveUserError):
        await get_current_active_user(mock_user)


@pytest.mark.asyncio
async def test_get_current_active_user_success() -> None:
    mock_user = User(id=1, is_active=True)
    res = await get_current_active_user(mock_user)
    assert res == mock_user


@pytest.mark.asyncio
async def test_get_current_verified_user_unverified() -> None:
    mock_user = User(id=1, is_active=True, is_verified=False)
    with pytest.raises(UnverifiedEmailError):
        await get_current_verified_user(mock_user)


@pytest.mark.asyncio
async def test_get_current_verified_user_success() -> None:
    mock_user = User(id=1, is_active=True, is_verified=True)
    res = await get_current_verified_user(mock_user)
    assert res == mock_user
