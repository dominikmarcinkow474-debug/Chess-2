import os
os.environ["DATABASE_URL"] = "sqlite:///./test_chess_companion.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests"
os.environ["STOCKFISH_PATH"] = "stockfish"
os.environ["STOCKFISH_DEPTH"] = "2"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
