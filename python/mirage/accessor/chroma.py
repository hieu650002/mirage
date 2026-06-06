import importlib
from typing import Any

from mirage.accessor.base import Accessor
from mirage.resource.chroma.config import ChromaConfig


class ChromaAccessor(Accessor):

    def __init__(self, config: ChromaConfig) -> None:
        self.config = config
        self._client: Any | None = None
        self._collection: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            chromadb = importlib.import_module("chromadb")

            if self.config.path is not None:
                self._client = chromadb.PersistentClient(path=self.config.path)
            else:
                self._client = chromadb.HttpClient(host=self.config.host,
                                                   port=self.config.port,
                                                   ssl=self.config.ssl)
        return self._client

    @property
    def collection(self) -> Any:
        if self._collection is None:
            self._collection = self.client.get_collection(
                self.config.collection_name)
        return self._collection
