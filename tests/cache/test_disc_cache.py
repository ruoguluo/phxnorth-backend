"""Tests for DISCProfileCache."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.cache.disc_cache import (
    DEFAULT_TTL_SECONDS,
    VALID_WINDOWS,
    DISCProfileCache,
    _disc_key,
)
from app.cache.redis_client import RedisCacheService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROFILE: dict[str, Any] = {
    "d": 72.5,
    "i": 45.3,
    "s": 38.1,
    "c": 60.0,
    "confidence": 0.85,
    "dominant": "D",
    "secondary": "C",
    "signal_count": 15,
    "computed_at": "2025-06-01T12:00:00+00:00",
    "model_version": "1.0",
}

USER_ID = "abc-123-def"


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock RedisCacheService with all async methods stubbed."""
    mock = AsyncMock(spec=RedisCacheService)
    mock.get_json = AsyncMock(return_value=None)
    mock.set_json = AsyncMock()
    mock.delete_pattern = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def cache(mock_redis: AsyncMock) -> DISCProfileCache:
    return DISCProfileCache(redis=mock_redis)


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------


class TestDiscKey:
    def test_builds_key_with_window(self) -> None:
        assert _disc_key("user-1", "90d") == "disc:user-1:90d"

    def test_builds_key_lifetime(self) -> None:
        assert _disc_key("user-1", "lifetime") == "disc:user-1:lifetime"


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    @pytest.mark.asyncio
    async def test_cache_hit(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get_json.return_value = SAMPLE_PROFILE

        result = await cache.get_profile(USER_ID, "90d")

        assert result == SAMPLE_PROFILE
        mock_redis.get_json.assert_awaited_once_with(
            _disc_key(USER_ID, "90d")
        )

    @pytest.mark.asyncio
    async def test_cache_miss(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get_json.return_value = None

        result = await cache.get_profile(USER_ID, "30d")

        assert result is None

    @pytest.mark.asyncio
    async def test_default_window_is_90d(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        await cache.get_profile(USER_ID)

        mock_redis.get_json.assert_awaited_once_with(
            _disc_key(USER_ID, "90d")
        )


# ---------------------------------------------------------------------------
# set_profile
# ---------------------------------------------------------------------------


class TestSetProfile:
    @pytest.mark.asyncio
    async def test_sets_with_default_ttl(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        await cache.set_profile(USER_ID, "90d", SAMPLE_PROFILE)

        mock_redis.set_json.assert_awaited_once_with(
            _disc_key(USER_ID, "90d"),
            SAMPLE_PROFILE,
            ttl_seconds=DEFAULT_TTL_SECONDS,
        )

    @pytest.mark.asyncio
    async def test_sets_with_custom_ttl(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        await cache.set_profile(USER_ID, "lifetime", SAMPLE_PROFILE, ttl=7200)

        mock_redis.set_json.assert_awaited_once_with(
            _disc_key(USER_ID, "lifetime"),
            SAMPLE_PROFILE,
            ttl_seconds=7200,
        )


# ---------------------------------------------------------------------------
# set_all_windows
# ---------------------------------------------------------------------------


class TestSetAllWindows:
    @pytest.mark.asyncio
    async def test_sets_all_three_windows(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        profiles = {
            "30d": {**SAMPLE_PROFILE, "d": 70.0},
            "90d": SAMPLE_PROFILE,
            "lifetime": {**SAMPLE_PROFILE, "d": 68.0},
        }

        await cache.set_all_windows(USER_ID, profiles)

        assert mock_redis.set_json.await_count == 3

    @pytest.mark.asyncio
    async def test_skips_missing_windows(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        """Only cache windows present in the profiles dict."""
        profiles = {"90d": SAMPLE_PROFILE}

        await cache.set_all_windows(USER_ID, profiles)

        assert mock_redis.set_json.await_count == 1

    @pytest.mark.asyncio
    async def test_ignores_extra_keys(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        """Unknown window labels are silently dropped."""
        profiles = {
            "90d": SAMPLE_PROFILE,
            "7d": SAMPLE_PROFILE,  # not a valid window
        }

        await cache.set_all_windows(USER_ID, profiles)

        assert mock_redis.set_json.await_count == 1


# ---------------------------------------------------------------------------
# invalidate
# ---------------------------------------------------------------------------


class TestInvalidate:
    @pytest.mark.asyncio
    async def test_deletes_pattern(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        mock_redis.delete_pattern.return_value = 3

        await cache.invalidate(USER_ID)

        mock_redis.delete_pattern.assert_awaited_once_with(
            f"disc:{USER_ID}:*"
        )


# ---------------------------------------------------------------------------
# get_or_compute
# ---------------------------------------------------------------------------


class TestGetOrCompute:
    @pytest.mark.asyncio
    async def test_returns_cached_on_hit(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get_json.return_value = SAMPLE_PROFILE
        compute_fn = AsyncMock(return_value={"should": "not be called"})

        result = await cache.get_or_compute(USER_ID, "90d", compute_fn)

        assert result == SAMPLE_PROFILE
        compute_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_computes_and_caches_on_miss(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get_json.return_value = None
        computed = {**SAMPLE_PROFILE, "d": 80.0}
        compute_fn = AsyncMock(return_value=computed)

        result = await cache.get_or_compute(USER_ID, "90d", compute_fn)

        assert result == computed
        compute_fn.assert_awaited_once()
        mock_redis.set_json.assert_awaited_once_with(
            _disc_key(USER_ID, "90d"),
            computed,
            ttl_seconds=DEFAULT_TTL_SECONDS,
        )

    @pytest.mark.asyncio
    async def test_respects_custom_ttl(
        self, cache: DISCProfileCache, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get_json.return_value = None
        compute_fn = AsyncMock(return_value=SAMPLE_PROFILE)

        await cache.get_or_compute(USER_ID, "30d", compute_fn, ttl=600)

        mock_redis.set_json.assert_awaited_once_with(
            _disc_key(USER_ID, "30d"),
            SAMPLE_PROFILE,
            ttl_seconds=600,
        )
