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

import fnmatch

from mirage.accessor.history import HistoryAccessor
from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.utils.output import format_records
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.core.history.read import _VIEW_KEYS
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec

_VIEW_NAME = ".bash_history"


@command("find", resource="history", spec=SPECS["find"])
async def find(
    accessor: HistoryAccessor,
    paths: list[PathSpec],
    *texts: str,
    stdin: bytes | None = None,
    name: str | None = None,
    type: str | None = None,
    iname: str | None = None,
    maxdepth: str | None = None,
    mindepth: str | None = None,
    index: IndexCacheStore = None,
    **_extra: object,
) -> tuple[ByteSource | None, IOResult]:
    if not paths:
        return format_records([]), IOResult()
    p0 = paths[0]
    key = p0.strip_prefix if isinstance(p0, PathSpec) else p0
    if key.strip("/") not in _VIEW_KEYS:
        raise FileNotFoundError(key)
    if type == "d":
        return format_records([]), IOResult()
    if mindepth is not None and int(mindepth) > 0:
        return format_records([]), IOResult()
    matcher = iname or name
    candidate = _VIEW_NAME.lower() if iname else _VIEW_NAME
    pattern = matcher.lower() if (iname and matcher) else matcher
    if pattern and not fnmatch.fnmatch(candidate, pattern):
        return format_records([]), IOResult()
    out = p0.original if isinstance(p0, PathSpec) else p0
    return format_records([out]), IOResult()
