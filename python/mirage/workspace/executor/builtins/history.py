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

from mirage.io.types import ByteSource, IOResult
from mirage.workspace.session.session import Session
from mirage.workspace.types import ExecutionNode

HISTORY_MOUNT = "/.bash_history"


async def handle_history(
    registry,
    args: list[str],
    session: Session,
) -> tuple[ByteSource | None, IOResult, ExecutionNode]:
    """Dispatch the history shell builtin to the view mount.

    GNU lookup order: builtins resolve before mount commands, so a
    mount-local command named "history" can never shadow this one.
    The actual rendering lives on the /.bash_history view resource;
    this handler only routes to it.

    Args:
        registry (MountRegistry): The workspace's mount registry.
        args (list[str]): Raw builtin args (flags and counts).
        session (Session): Calling session.
    """
    try:
        mount = registry.mount_for(HISTORY_MOUNT)
    except ValueError:
        err = b"history: not enabled for this workspace\n"
        return None, IOResult(exit_code=1,
                              stderr=err), ExecutionNode(command="history",
                                                         exit_code=1,
                                                         stderr=err)
    flags = {"c": True} if "-c" in args else {}
    texts = [a for a in args if a != "-c"]
    stream, io = await mount.execute_cmd("history", [],
                                         texts,
                                         flags,
                                         session_id=session.session_id)
    return stream, io, ExecutionNode(command="history",
                                     exit_code=io.exit_code,
                                     stderr=io.stderr)
