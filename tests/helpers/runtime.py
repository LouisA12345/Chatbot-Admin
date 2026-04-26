"""Runtime helpers for isolated pytest imports and dependency stubbing."""

from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def reset_chatbot_modules() -> None:
    """Remove cached chatbot modules so each test can import a clean graph."""
    for name in list(sys.modules):
        if name == "chatbot_app" or name.startswith("chatbot_app."):
            sys.modules.pop(name)


def install_external_dependency_stubs() -> None:
    """Install lightweight stand-ins for optional runtime dependencies."""

    class FakeIndexFlatL2:
        def __init__(self, dim: int):
            self.dim = dim
            self.vectors = np.empty((0, dim), dtype="float32")

        def add(self, vectors):
            array = np.array(vectors, dtype="float32")
            if array.ndim == 1:
                array = array.reshape(1, -1)
            self.vectors = np.vstack([self.vectors, array])

        def search(self, query_vectors, top_k: int):
            query_array = np.array(query_vectors, dtype="float32")
            if query_array.ndim == 1:
                query_array = query_array.reshape(1, -1)
            if len(self.vectors) == 0:
                distances = np.full((len(query_array), top_k), np.inf, dtype="float32")
                indices = np.full((len(query_array), top_k), -1, dtype="int64")
                return distances, indices

            all_distances = []
            all_indices = []
            for query in query_array:
                distances = np.linalg.norm(self.vectors - query, axis=1) ** 2
                order = np.argsort(distances)[:top_k]
                padded_distances = np.full(top_k, np.inf, dtype="float32")
                padded_indices = np.full(top_k, -1, dtype="int64")
                padded_distances[: len(order)] = distances[order]
                padded_indices[: len(order)] = order
                all_distances.append(padded_distances)
                all_indices.append(padded_indices)
            return np.array(all_distances), np.array(all_indices)

    def read_index(path: str):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        index = FakeIndexFlatL2(data["dim"])
        if data["vectors"]:
            index.add(np.array(data["vectors"], dtype="float32"))
        return index

    def write_index(index, path: str):
        payload = {
            "dim": index.dim,
            "vectors": index.vectors.tolist(),
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    faiss_module = types.ModuleType("faiss")
    faiss_module.IndexFlatL2 = FakeIndexFlatL2
    faiss_module.read_index = read_index
    faiss_module.write_index = write_index
    sys.modules["faiss"] = faiss_module

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def encode(self, texts):
            if isinstance(texts, str):
                texts = [texts]
            vectors = []
            for text in texts:
                lower = text.lower()
                vectors.append(
                    [
                        float("apple" in lower),
                        float("car" in lower),
                        float("order" in lower),
                        float(bool(lower.strip())),
                    ]
                )
            return np.array(vectors, dtype="float32")

    sentence_module = types.ModuleType("sentence_transformers")
    sentence_module.SentenceTransformer = FakeSentenceTransformer
    sys.modules["sentence_transformers"] = sentence_module

    class FakeCompletionResponse:
        def __init__(self, content: str):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]

    class FakeCompletions:
        response_content = '{"message": "Stubbed response", "options": [], "links": [], "db_action": null}'

        def create(self, **_kwargs):
            return FakeCompletionResponse(self.response_content)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.chat = SimpleNamespace(completions=FakeCompletions())

    groq_module = types.ModuleType("groq")
    groq_module.Groq = FakeGroq
    sys.modules["groq"] = groq_module

    class FakePage:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self):
            return self._text

    class FakePdfReader:
        def __init__(self, file_path):
            path = Path(file_path)
            text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
            self.pages = [FakePage(text or "Stub PDF content for tests.")]

    pypdf_module = types.ModuleType("pypdf")
    pypdf_module.PdfReader = FakePdfReader
    sys.modules["pypdf"] = pypdf_module


def import_fresh(module_name: str):
    """Import a chatbot module after clearing cached copies and stubbing deps."""
    reset_chatbot_modules()
    install_external_dependency_stubs()
    os.environ["ADMIN_API_KEY"] = os.environ.get("ADMIN_API_KEY", "test-admin-key")
    return importlib.import_module(module_name)


def bootstrap_app(monkeypatch, tmp_path):
    """Create an isolated Flask app with temporary data and database paths."""
    reset_chatbot_modules()
    install_external_dependency_stubs()
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")

    config = importlib.import_module("chatbot_app.config")
    data_dir = tmp_path / "data"
    customer_db = tmp_path / "customer.db"
    owner_db = tmp_path / "owner.db"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "CUSTOMER_DB_PATH", customer_db)
    monkeypatch.setattr(config, "OWNER_DB_PATH", owner_db)

    app_pkg = importlib.import_module("chatbot_app")
    auth_module = importlib.import_module("chatbot_app.routes.auth")
    site_store_module = importlib.import_module("chatbot_app.services.site_store")
    admin_module = importlib.import_module("chatbot_app.routes.admin")
    chat_route_module = importlib.import_module("chatbot_app.routes.chat")
    chat_service_module = importlib.import_module("chatbot_app.services.chat_service")
    db_service_module = importlib.import_module("chatbot_app.db.service")
    ai_engine_module = importlib.import_module("chatbot_app.ai.engine")

    # Some modules import config paths by value during module import, so patch
    # them explicitly here to keep every integration test inside tmp_path.
    monkeypatch.setattr(auth_module, "CUSTOMER_DB_PATH", customer_db)
    monkeypatch.setattr(auth_module, "OWNER_DB_PATH", owner_db)
    monkeypatch.setattr(site_store_module, "DATA_DIR", data_dir)
    site_store_module.DATA_DIR.mkdir(parents=True, exist_ok=True)
    site_store_module.site_stores.clear()

    app = app_pkg.create_app()

    return SimpleNamespace(
        app=app,
        config=config,
        data_dir=data_dir,
        customer_db=customer_db,
        owner_db=owner_db,
        auth=auth_module,
        admin=admin_module,
        chat_route=chat_route_module,
        chat_service=chat_service_module,
        site_store=site_store_module,
        db_service=db_service_module,
        ai_engine=ai_engine_module,
    )
