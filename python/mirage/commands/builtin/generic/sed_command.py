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
"""Factory for the per-backend ``sed`` commands.

Every backend's ``sed`` is the same logic over the generic engine, differing
only in how bytes are read, whether globs are resolved (and under what
condition), whether the mount is writable, and the ``-i`` rejection. ``make_sed``
captures that so each backend is a small config instead of a copy-pasted body.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

from mirage.cache.index import IndexCacheStore
from mirage.commands.builtin.generic.sed import sed as generic_sed
from mirage.commands.registry import command
from mirage.commands.spec import SPECS
from mirage.io.types import ByteSource, IOResult
from mirage.types import PathSpec

# (accessor, index, resolved_paths) -> read_bytes callable for generic_sed.
MakeRead = Callable[[object, IndexCacheStore | None, list[PathSpec]], Callable]
# (accessor, index) -> whether to resolve globs (paths already known truthy).
GlobWhen = Callable[[object, IndexCacheStore | None], bool]


def make_sed(
    *,
    resource: str | list[str],
    glob_fn: Callable[..., Awaitable[list[PathSpec]]],
    make_read: MakeRead,
    glob_when: GlobWhen | None = None,
    write_bytes: Callable[..., Awaitable[None]] | None = None,
    inplace_error: tuple[type[Exception], str] | None = None,
) -> Callable:
    @command("sed", resource=resource, spec=SPECS["sed"])
    async def sed(
        accessor: object,
        paths: list[PathSpec],
        *texts: str,
        stdin: AsyncIterator[bytes] | bytes | None = None,
        i: bool = False,
        e: bool = False,
        n: bool = False,
        E: bool = False,
        index: IndexCacheStore = None,
        **_extra: object,
    ) -> tuple[ByteSource | None, IOResult]:
        if not texts:
            raise ValueError("sed: usage: sed EXPRESSION [path]")
        if inplace_error is not None and i:
            exc_type, message = inplace_error
            raise exc_type(message)
        if paths and (glob_when is None or glob_when(accessor, index)):
            paths = await glob_fn(accessor, paths, index)
        elif inplace_error is None:
            # Writable mounts treat a non-glob invocation as stdin mode; the
            # read-only mounts leave the operands untouched (mirroring the
            # original per-backend wrappers).
            paths = []
        return await generic_sed(
            paths,
            texts[0],
            read_bytes=make_read(accessor, index, paths),
            write_bytes=write_bytes,
            accessor=accessor,
            stdin=stdin,
            in_place=i,
            suppress=n,
            extended=E or bool(_extra.get("r", False)),
            index=index,
        )

    return sed


__all__ = ["make_sed"]
