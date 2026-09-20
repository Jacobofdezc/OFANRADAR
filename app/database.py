import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Try loading .env and .env.local if available
try:
    from dotenv import load_dotenv
    base_dir = os.path.dirname(os.path.dirname(__file__))
    load_dotenv(os.path.join(base_dir, ".env.local"))
    load_dotenv(os.path.join(base_dir, ".env"))
except ImportError:
    pass

env_db_url = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dvgqgposoapimwsemzgx.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Determine database engine and URL
use_postgres = False
if env_db_url and "[YOUR-PASSWORD]" not in env_db_url and "YOUR-PASSWORD" not in env_db_url:
    if env_db_url.startswith("postgres://"):
        env_db_url = env_db_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = env_db_url
    use_postgres = True
    engine_kwargs = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
else:
    # SQLite Fallback (local or serverless /tmp)
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
