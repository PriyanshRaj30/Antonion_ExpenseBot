from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
import uuid

class Transaction(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str
    amount: float
    category: str
    description: str
    is_unnecessary: bool
    tx_type: str = Field(default="expense") 

    date: datetime = Field(default_factory=datetime.utcnow)

