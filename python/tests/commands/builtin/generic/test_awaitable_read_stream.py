import hashlib

import pytest

from mirage.commands.builtin.generic.cut import cut
from mirage.commands.builtin.generic.sha256sum import sha256sum
from mirage.types import PathSpec

_DATA = b"a b c\nd e f\n"


async def _gdrive_read_stream(accessor, path):
    """Mimic gdrive: a plain ``async def`` resolving to ``bytes`` (not an
    async generator), which crashed generic streaming commands cold."""
    return _DATA


async def _gdrive_read_bytes(accessor, path):
    return _DATA


def _path():
    return PathSpec(original="/g/doc", directory="/g")


@pytest.mark.asyncio
async def test_cut_handles_awaitable_bytes_read_stream():
    out, _ = await cut([_path()],
                       read_stream=_gdrive_read_stream,
                       accessor=None,
                       f="1",
                       d=" ")
    collected = b"".join([chunk async for chunk in out])
    assert collected == b"a\nd\n"


@pytest.mark.asyncio
async def test_sha256sum_handles_awaitable_bytes_read_stream():
    out, _ = await sha256sum([_path()],
                             read_bytes=_gdrive_read_bytes,
                             read_stream=_gdrive_read_stream,
                             accessor=None)
    collected = b"".join([chunk async for chunk in out])
    assert hashlib.sha256(_DATA).hexdigest().encode() in collected
