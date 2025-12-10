# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite lokal baza (fayl: agro.db)
SQLALCHEMY_DATABASE_URL = "sqlite:///./agro.db"

# SQLite uchun maxsus parametr (multi-thread uchun)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # faqat SQLite uchun
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency.
    Endpointlarda:
        db: Session = Depends(get_db)
    deb ishlatiladi.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
