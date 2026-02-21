from sqlmodel import SQLModel, create_engine

DATABASE_URL = "sqlite:///expenses.db"

engine = create_engine(DATABASE_URL, echo=True)

def create_db():
    SQLModel.metadata.create_all(engine)
