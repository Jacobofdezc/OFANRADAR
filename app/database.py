import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

env_db_url = os.getenv("DATABASE_URL")

if env_db_url:
    if env_db_url.startswith("postgres://"):
        env_db_url = env_db_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = env_db_url
    engine_kwargs = {}
else:
    if os.getenv("VERCEL"):
        DB_PATH = "/tmp/radar.db"
    else:
        DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "radar.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
