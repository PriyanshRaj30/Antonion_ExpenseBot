from sqlmodel import Session, select
from database import engine
from models import Transaction

def test_select():
    with Session(engine) as session:
        statement = select(Transaction)
        results = session.exec(statement).all()

        if not results:
            print("No transactions found.")
            return

        print("Transactions in DB:")
        for tx in results:
            print("------------------------")
            print("ID:", tx.id)
            print("User:", tx.user_id)
            print("Amount:", tx.amount)
            print("Category:", tx.category)
            print("Description:", tx.description)
            print("Unnecessary:", tx.is_unnecessary)
            print("Date:", tx.date)

if __name__ == "__main__":
    test_select()
