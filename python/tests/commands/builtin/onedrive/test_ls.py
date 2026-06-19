from importlib import import_module

import pytest

from mirage.accessor.onedrive import OneDriveAccessor, OneDriveConfig
from mirage.io.types import materialize
from mirage.types import FileStat, FileType, PathSpec

ls_mod = import_module("mirage.commands.builtin.onedrive.ls")


def _accessor() -> OneDriveAccessor:
    return OneDriveAccessor(OneDriveConfig(access_token="tok"))


async def _resolve_paths(accessor, paths, index):
    return paths


async def _readdir(accessor, path, index):
    return ["/Docs"]


async def _stat(accessor, path, index):
    return FileStat(name="Docs", type=FileType.DIRECTORY)


@pytest.mark.asyncio
async def test_ls_delegates_to_generic_without_extra_keywords(monkeypatch):
    monkeypatch.setattr(ls_mod, "resolve_glob", _resolve_paths)
    monkeypatch.setattr(ls_mod, "readdir", _readdir)
    monkeypatch.setattr(ls_mod, "stat", _stat)

    stdout, io = await ls_mod.ls(_accessor(), [PathSpec.from_str_path("/")])

    assert await materialize(stdout) == b"Docs\n"
    assert io.exit_code == 0
