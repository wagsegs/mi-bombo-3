import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database


class FakeConn:
    def __init__(self):
        self.executed = []
        self.released = False

    async def execute(self, *args, **kwargs):
        self.executed.append((args, kwargs))

    async def fetchrow(self, *args, **kwargs):
        return None


class FakePool:
    def __init__(self):
        self.acquired = []
        self.released = []
        self.closed = False

    async def acquire(self):
        conn = FakeConn()
        self.acquired.append(conn)
        return conn

    async def release(self, conn):
        self.released.append(conn)
        conn.released = True

    async def close(self):
        self.closed = True


def test_connect_reuses_existing_pool(monkeypatch):
    created = []

    async def fake_create_pool(*args, **kwargs):
        created.append((args, kwargs))
        return FakePool()

    monkeypatch.setattr(database.asyncpg, "create_pool", fake_create_pool)
    database._pool = None

    asyncio.run(database.connect("postgres://example"))
    asyncio.run(database.connect("postgres://example"))

    assert len(created) == 1


def test_save_message_releases_connection_back_to_pool(monkeypatch):
    fake_pool = FakePool()
    database._pool = fake_pool

    asyncio.run(database.save_message(1, 2, "user", None, 3, "general", "hello"))

    assert len(fake_pool.acquired) == 1
    assert len(fake_pool.released) == 1
    assert fake_pool.acquired[0].released


def test_disconnect_closes_pool_and_clears_reference():
    fake_pool = FakePool()
    database._pool = fake_pool

    asyncio.run(database.disconnect())

    assert fake_pool.closed is True
    assert database._pool is None
