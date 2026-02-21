from sqlmodel import Session
from models import Transaction
from database import engine

def save_transaction(data):
    with Session(engine) as session:
        tx = Transaction(**data)
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return tx
