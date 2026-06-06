# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

import pytest

from mirage.cache.file.ram import RAMFileCacheStore


def test_cache_fork_fresh_drain_tasks_and_size():
    parent = RAMFileCacheStore()
    child = parent.fork()
    assert child.cache_size == parent.cache_size
    assert child._drain_tasks is not parent._drain_tasks
    assert child._drain_tasks == {}
    assert child._entries is not parent._entries


@pytest.mark.asyncio
async def test_cache_fork_payload_shared_then_isolated():
    parent = RAMFileCacheStore()
    await parent.set("/a", b"hello")
    child = parent.fork()
    assert await child.get("/a") == b"hello"
    assert child._store.files["/a"] is parent._store.files["/a"]

    await child.set("/a", b"world")
    assert await parent.get("/a") == b"hello"
    assert await child.get("/a") == b"world"

    await child.remove("/a")
    assert await parent.get("/a") == b"hello"

    await child.set("/b", b"x")
    assert await parent.get("/b") is None


@pytest.mark.asyncio
async def test_cache_fork_size_accounting_diverges():
    parent = RAMFileCacheStore()
    await parent.set("/a", b"hello")
    base = parent.cache_size
    child = parent.fork()
    await child.set("/b", b"world")
    assert child.cache_size > base
    assert parent.cache_size == base


def test_redis_cache_fork_raises():
    pytest.importorskip("redis")
    from mirage.cache.file.redis import RedisFileCacheStore

    # fork() refuses before any I/O, so call the unbound method with a
    # dummy self to exercise the contract without a live Redis server.
    with pytest.raises(NotImplementedError):
        RedisFileCacheStore.fork(object())
