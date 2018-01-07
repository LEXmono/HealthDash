from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    avatar = Column(String(200))
    active = Column(Boolean, default=False)
    tokens = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow()


