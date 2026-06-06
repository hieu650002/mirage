import pytest

from mirage.core.chroma import read


@pytest.mark.asyncio
async def test_read_bytes_reassembles_sorted_chunks(chroma_accessor,
                                                    chroma_index,
                                                    quickstart_path):
    data = await read.read_bytes(chroma_accessor, quickstart_path,
                                 chroma_index)

    assert data == b"first\nsecond"


@pytest.mark.asyncio
async def test_read_stream_yields_sorted_chunks(chroma_accessor, chroma_index,
                                                quickstart_path):
    chunks = [
        chunk async for chunk in read.read_stream(
            chroma_accessor, quickstart_path, chroma_index)
    ]

    assert chunks == [b"first", b"\n", b"second"]


@pytest.mark.asyncio
async def test_read_bytes_rejects_directories(chroma_accessor, chroma_index,
                                              knowledge_root):
    with pytest.raises(IsADirectoryError):
        await read.read_bytes(chroma_accessor, knowledge_root, chroma_index)
