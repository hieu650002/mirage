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

import asyncio
import json

from mirage import MountMode, Workspace
from mirage.resource.ram import RAMResource


def test_workspace_creates_default_observer():
    ws = Workspace({"/data/": RAMResource()}, mode=MountMode.WRITE)
    assert ws.observer is not None


def test_workspace_custom_observe_resource():
    obs_resource = RAMResource()
    ws = Workspace(
        {"/data/": RAMResource()},
        mode=MountMode.WRITE,
        observe=obs_resource,
    )
    assert ws.observer.resource is obs_resource


def test_logs_populated_after_execute():
    ws = Workspace({"/data/": RAMResource()}, mode=MountMode.WRITE)
    asyncio.run(ws.execute("echo hello > /data/test.txt"))
    obs_store = ws.observer.resource._store
    session_files = [k for k in obs_store.files if k.endswith(".jsonl")]
    assert len(session_files) >= 1
    data = obs_store.files[session_files[0]]
    lines = data.decode().strip().split("\n")
    assert len(lines) >= 1
    entry = json.loads(lines[-1])
    assert entry["type"] == "command"


def test_logs_contain_op_records():
    ws = Workspace({"/data/": RAMResource()}, mode=MountMode.WRITE)
    asyncio.run(ws.execute("echo hello > /data/test.txt"))
    asyncio.run(ws.execute("cat /data/test.txt"))
    obs_store = ws.observer.resource._store
    session_files = [k for k in obs_store.files if k.endswith(".jsonl")]
    data = obs_store.files[session_files[0]]
    lines = data.decode().strip().split("\n")
    types = {json.loads(line)["type"] for line in lines}
    assert "op" in types
    assert "command" in types


def test_observer_store_not_mounted():
    ws = Workspace({"/data/": RAMResource()}, mode=MountMode.WRITE)
    asyncio.run(ws.execute("echo hi > /data/f.txt"))
    result = asyncio.run(ws.execute("ls /.sessions"))
    assert result.exit_code != 0
    mounted = {m.resource for m in ws._registry.mounts()}
    assert ws.observer.resource not in mounted
