import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_runtime(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("database") / "test.db"

    with pytest.MonkeyPatch.context() as patch:
        # Set these before importing the application.
        patch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        patch.setenv("SECRET_KEY", "test-only-secret-" + "a" * 64)
        patch.setenv("ALGORITHM", "HS256")

        from order_utils import storage

        # Never reset a database unless it is our test database.
        assert storage.engine.url.database == db_path.as_posix()

        from main import app
        from order_utils.models import Base

        try:
            yield app, storage, Base
        finally:
            storage.engine.dispose()


@pytest.fixture
def client(test_runtime):
    app, storage, Base = test_runtime

    Base.metadata.drop_all(storage.engine)
    Base.metadata.create_all(storage.engine)

    from order_utils.models import (
        InventoryRow,
        ProductRow,
        InventoryProductRow,
    )

    with storage.get_db_write() as db:
        db.add(InventoryRow(id=1, name="Test inventory"))
        db.add(ProductRow(id="test-product", name="Test product"))
        db.flush()

        db.add(
            InventoryProductRow(
                inventory_id=1,
                product_id="test-product",
                stock=10,
                unit_price=50
            )
        )

    with TestClient(app) as test_client:
        yield test_client