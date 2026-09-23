import tempfile
import unittest
from unittest.mock import patch

from backend.rag_service import LabRAGService


class FakeModel:
    def __init__(self, name):
        self.name = name
        self.inputs = []

    def encode(self, inputs, normalize_embeddings):
        self.inputs.extend(inputs)
        self.normalize_embeddings = normalize_embeddings
        return [[float(index)] for index, _ in enumerate(inputs)]


class FakeCollection:
    def __init__(self, metadata):
        self.metadata = metadata
        self.documents = []
        self.added_embeddings = []
        self.query_embeddings = []

    def count(self):
        return len(self.documents)

    def add(self, documents, embeddings, metadatas, ids):
        self.documents.extend(documents)
        self.added_embeddings = embeddings

    def query(self, query_embeddings, n_results):
        self.query_embeddings = query_embeddings
        return {"documents": [[self.documents[0]]]}


class FakeClient:
    def __init__(self, collection=None):
        self.collection = collection
        self.deleted = []

    def get_collection(self, name):
        if self.collection is None:
            raise ValueError("missing collection")
        return self.collection

    def delete_collection(self, name):
        self.deleted.append(name)
        self.collection = None

    def get_or_create_collection(self, name, metadata):
        self.collection = FakeCollection(metadata)
        return self.collection


class RagEmbeddingTests(unittest.TestCase):
    def build_service(self, client, model_name="intfloat/multilingual-e5-small"):
        with patch("backend.rag_service.SentenceTransformer", FakeModel), patch(
            "backend.rag_service.chromadb.PersistentClient", return_value=client
        ), patch.dict("os.environ", {"EMBEDDING_MODEL": model_name}):
            return LabRAGService(tempfile.mkdtemp())

    def test_uses_e5_prefixes_and_explicit_embeddings(self):
        client = FakeClient()
        service = self.build_service(client)

        service.search_knowledge_base("pricing", n_results=1)

        self.assertTrue(service.model.inputs[0].startswith("passage: "))
        self.assertTrue(service.model.inputs[-1].startswith("query: "))
        self.assertTrue(client.collection.added_embeddings)
        self.assertTrue(client.collection.query_embeddings)
        self.assertTrue(service.model.normalize_embeddings)

    def test_rebuilds_collection_when_model_changes(self):
        old = FakeCollection({"embedding_model": "old-model"})
        client = FakeClient(old)

        service = self.build_service(client, "intfloat/multilingual-e5-small")

        self.assertEqual(client.deleted, ["kb_intfloat_multilingual-e5-small"])
        self.assertEqual(service.collection.metadata["embedding_model"], "intfloat/multilingual-e5-small")


if __name__ == "__main__":
    unittest.main()
