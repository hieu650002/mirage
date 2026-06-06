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

import tempfile
from pathlib import Path

import pytest

from mirage.resource.disk import DiskResource
from mirage.resource.ram import RAMResource
from mirage.types import DEFAULT_SESSION_ID, MountMode
from mirage.workspace import Workspace


class _SharedRAM(RAMResource):
    """RAM backend that forks by sharing — mimics a live remote backend
    (S3, Slack, ...) whose `fork()` is the BaseResource share-by-ref
    default."""

    def fork(self) -> "_SharedRAM":
        return self


class _FakeRedisCache:
    """Stand-in so the Redis-cache guard can be exercised without a live
    Redis server (a real RedisFileCacheStore connects on construction)."""


def _ws() -> Workspace:
    ram = RAMResource()
    ram._store.files["/seed.txt"] = b"seed\n"
    ws = Workspace(
        {"/ram/": (ram, MountMode.EXEC)},
        history=None,
    )
    ws.get_session(DEFAULT_SESSION_ID).cwd = "/ram"
    return ws


def _files(ws, prefix="/ram"):
    return ws.mount(prefix).resource._store.files


def _dirs(ws, prefix="/ram"):
    return ws.mount(prefix).resource._store.dirs


@pytest.mark.asyncio
async def test_fork_inherits_parent_ram_content():
    ws = _ws()
    child = await ws.fork()
    result = await child.execute("cat /ram/seed.txt")
    assert b"seed" in result.stdout


@pytest.mark.asyncio
async def test_fork_ram_write_does_not_leak_to_parent():
    ws = _ws()
    child = await ws.fork()
    await child.execute("echo hi > /ram/a.txt")
    assert "/a.txt" in child.mount("/ram").resource._store.files
    assert "/a.txt" not in ws.mount("/ram").resource._store.files


@pytest.mark.asyncio
async def test_fork_parent_write_does_not_leak_to_child():
    ws = _ws()
    child = await ws.fork()
    await ws.execute("echo bye > /ram/b.txt")
    assert "/b.txt" in ws.mount("/ram").resource._store.files
    assert "/b.txt" not in child.mount("/ram").resource._store.files


@pytest.mark.asyncio
async def test_fork_session_cwd_inherited_then_isolated():
    ws = _ws()
    child = await ws.fork()
    assert child.get_session(DEFAULT_SESSION_ID).cwd == "/ram"
    child.get_session(DEFAULT_SESSION_ID).cwd = "/"
    assert ws.get_session(DEFAULT_SESSION_ID).cwd == "/ram"


@pytest.mark.asyncio
async def test_fork_shares_remote_style_resource():
    shared = _SharedRAM()
    ws = Workspace({"/s3/": (shared, MountMode.EXEC)}, history=None)
    ws.get_session(DEFAULT_SESSION_ID).cwd = "/s3"
    child = await ws.fork()
    assert child.mount("/s3").resource is shared
    await child.execute("echo hi > /s3/r.txt")
    assert "/r.txt" in shared._store.files


@pytest.mark.asyncio
async def test_fork_copies_history_then_diverges():
    ws = Workspace({"/ram/": (RAMResource(), MountMode.EXEC)}, history=100)
    await ws.execute("echo hi > /ram/a.txt")
    child = await ws.fork()
    assert len(child.history.entries()) == len(ws.history.entries())
    await child.execute("echo bye > /ram/b.txt")
    assert len(child.history.entries()) == len(ws.history.entries()) + 1


@pytest.mark.asyncio
async def test_fork_on_closed_workspace_raises():
    ws = _ws()
    await ws.close()
    with pytest.raises(RuntimeError):
        await ws.fork()


@pytest.mark.asyncio
async def test_fork_rejects_redis_backed_cache(monkeypatch):
    monkeypatch.setattr("mirage.workspace.fork.RedisFileCacheStore",
                        _FakeRedisCache)
    ws = _ws()
    ws._cache = _FakeRedisCache()
    with pytest.raises(NotImplementedError):
        await ws.fork()


@pytest.mark.asyncio
async def test_fork_child_overwrite_of_inherited_is_isolated():
    ws = _ws()
    child = await ws.fork()
    await child.execute("echo changed > /ram/seed.txt")
    assert (await ws.execute("cat /ram/seed.txt")).stdout == b"seed\n"
    assert b"changed" in (await child.execute("cat /ram/seed.txt")).stdout


@pytest.mark.asyncio
async def test_fork_child_delete_of_inherited_is_isolated():
    ws = _ws()
    child = await ws.fork()
    await child.execute("rm /ram/seed.txt")
    assert "/seed.txt" in _files(ws)
    assert "/seed.txt" not in _files(child)


@pytest.mark.asyncio
async def test_fork_child_append_to_inherited_is_isolated():
    ws = _ws()
    child = await ws.fork()
    await child.execute("echo more >> /ram/seed.txt")
    assert (await ws.execute("cat /ram/seed.txt")).stdout == b"seed\n"
    child_out = (await child.execute("cat /ram/seed.txt")).stdout
    assert b"seed" in child_out and b"more" in child_out


@pytest.mark.asyncio
async def test_fork_shares_payload_by_reference_with_cow_granularity():
    ws = _ws()
    await ws.execute("echo bbb > /ram/b.txt")
    child = await ws.fork()
    assert _files(child)["/seed.txt"] is _files(ws)["/seed.txt"]
    assert _files(child)["/b.txt"] is _files(ws)["/b.txt"]
    await child.execute("echo b2 > /ram/b.txt")
    assert _files(child)["/b.txt"] != _files(ws)["/b.txt"]
    assert _files(child)["/seed.txt"] is _files(ws)["/seed.txt"]
    assert _files(ws)["/b.txt"] == b"bbb\n"


@pytest.mark.asyncio
async def test_fork_grandchild_three_level_isolation():
    ws = _ws()
    await ws.execute("echo a > /ram/a.txt")
    child = await ws.fork()
    await child.execute("echo b > /ram/b.txt")
    grand = await child.fork()
    await grand.execute("echo c > /ram/c.txt")
    assert "/a.txt" in _files(grand) and "/b.txt" in _files(grand)
    assert "/c.txt" not in _files(child)
    assert "/b.txt" not in _files(ws) and "/c.txt" not in _files(ws)


@pytest.mark.asyncio
async def test_fork_two_siblings_isolated():
    ws = _ws()
    a = await ws.fork()
    b = await ws.fork()
    await a.execute("echo a > /ram/a.txt")
    await b.execute("echo b > /ram/b.txt")
    assert "/b.txt" not in _files(a)
    assert "/a.txt" not in _files(b)
    assert "/a.txt" not in _files(ws) and "/b.txt" not in _files(ws)


@pytest.mark.asyncio
async def test_fork_dirs_isolation_via_mkdir():
    ws = _ws()
    await ws.execute("mkdir /ram/d")
    child = await ws.fork()
    await child.execute("mkdir /ram/e")
    assert "/d" in _dirs(ws) and "/e" not in _dirs(ws)
    assert "/d" in _dirs(child) and "/e" in _dirs(child)


@pytest.mark.asyncio
async def test_fork_cross_mount_cp_isolated():
    ws = Workspace(
        {
            "/a/": (RAMResource(), MountMode.EXEC),
            "/b/": (RAMResource(), MountMode.EXEC),
        },
        history=None,
    )
    await ws.execute("echo data > /a/x.txt")
    child = await ws.fork()
    await child.execute("cp /a/x.txt /b/y.txt")
    assert "/y.txt" in _files(child, "/b")
    assert "/y.txt" not in _files(ws, "/b")


@pytest.mark.asyncio
async def test_fork_disk_eager_copy_distinct_root_and_isolated():
    root = tempfile.mkdtemp(prefix="mirage-test-disk-")
    ws = Workspace({"/disk/": (DiskResource(root=root), MountMode.EXEC)},
                   history=None)
    ws.get_session(DEFAULT_SESSION_ID).cwd = "/disk"
    await ws.execute("echo parent > /disk/p.txt")
    child = await ws.fork()
    proot = Path(ws.mount("/disk").resource.root)
    croot = Path(child.mount("/disk").resource.root)
    assert proot != croot
    await child.execute("echo child > /disk/c.txt")
    assert not (proot / "c.txt").exists()
    assert (croot / "p.txt").exists()


@pytest.mark.asyncio
async def test_fork_session_env_inherited_then_isolated():
    ws = _ws()
    ws.get_session(DEFAULT_SESSION_ID).env["FOO"] = "bar"
    child = await ws.fork()
    assert child.get_session(DEFAULT_SESSION_ID).env.get("FOO") == "bar"
    child.get_session(DEFAULT_SESSION_ID).env["FOO"] = "baz"
    assert ws.get_session(DEFAULT_SESSION_ID).env["FOO"] == "bar"


@pytest.mark.asyncio
async def test_fork_nondefault_session_inherited_and_isolated():
    ws = _ws()
    sess = ws.create_session("work")
    sess.env["K"] = "v"
    child = await ws.fork()
    assert child.get_session("work").env.get("K") == "v"
    child.get_session("work").env["K"] = "changed"
    assert ws.get_session("work").env["K"] == "v"


@pytest.mark.asyncio
async def test_fork_cache_distinct_and_isolated():
    ws = _ws()
    await ws._cache.set("/seedcache", b"v")
    child = await ws.fork()
    assert child._cache is not ws._cache
    assert await child._cache.get("/seedcache") == b"v"
    await child._cache.set("/probe", b"x")
    assert await ws._cache.get("/probe") is None
    await child._cache.remove("/seedcache")
    assert await ws._cache.get("/seedcache") == b"v"


@pytest.mark.asyncio
async def test_fork_has_isolated_observer():
    ws = _ws()
    child = await ws.fork()
    assert child.observer is not ws.observer
    assert child.observer.resource is not ws.observer.resource


@pytest.mark.asyncio
async def test_fork_parent_usable_after_fork_snapshot_at_fork():
    ws = _ws()
    child = await ws.fork()
    await ws.execute("echo a2 > /ram/post.txt")
    assert "/post.txt" in _files(ws)
    assert "/post.txt" not in _files(child)
