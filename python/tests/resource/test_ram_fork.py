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

from mirage.resource.base import BaseResource
from mirage.resource.ram import RAMResource
from mirage.resource.ram.store import RAMStore


def test_store_fork_shares_payload_by_reference():
    parent = RAMStore(files={"/a": b"hello"},
                      dirs={"/", "/d"},
                      modified={"/a": "t"})
    child = parent.fork()
    assert child.files["/a"] is parent.files["/a"]
    assert child.dirs == parent.dirs
    assert child.modified == parent.modified


def test_store_fork_write_isolates():
    parent = RAMStore(files={"/a": b"hello"})
    child = parent.fork()
    child.files["/a"] = b"world"
    child.files["/b"] = b"new"
    assert parent.files["/a"] == b"hello"
    assert "/b" not in parent.files


def test_store_fork_delete_isolates():
    parent = RAMStore(files={"/a": b"hello"})
    child = parent.fork()
    del child.files["/a"]
    assert "/a" in parent.files


def test_store_fork_dirs_isolate():
    parent = RAMStore(dirs={"/"})
    child = parent.fork()
    child.dirs.add("/sub")
    assert "/sub" not in parent.dirs


def test_resource_fork_independent_store_and_index():
    parent = RAMResource()
    child = parent.fork()
    assert child._store is not parent._store
    assert child.accessor.store is child._store
    assert child.index is not parent.index


def test_resource_fork_shares_bytes_then_isolates():
    parent = RAMResource()
    parent._store.files["/a"] = b"hello"
    child = parent.fork()
    assert child._store.files["/a"] is parent._store.files["/a"]
    child._store.files["/a"] = b"bye"
    assert parent._store.files["/a"] == b"hello"


def test_base_resource_fork_shares_by_reference():
    r = BaseResource()
    assert r.fork() is r
