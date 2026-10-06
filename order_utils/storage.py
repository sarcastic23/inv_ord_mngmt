from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import  create_engine,event
from sqlalchemy.orm import sessionmaker






db_path = Path(__file__).resolve().parent / "business.db"
engine = create_engine(f"sqlite:///{db_path.as_posix()}", echo=False)


SessionLocal = sessionmaker(bind=engine)


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_dependency():
    with get_db() as db:
        yield db



@contextmanager
def get_db_write():
    with get_db() as db:
        with db.begin():
            # Block other writers before reading and updating data.
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield db

@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()







