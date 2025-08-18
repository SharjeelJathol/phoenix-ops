from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

Base = declarative_base()

class CommandLog(Base):
    __tablename__ = 'command_log'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    command = Column(String(50))
    user_id = Column(Integer)
    user_role = Column(String(100))
    status = Column(String(20))
    duration_ms = Column(Integer, nullable=True)
    trunk_id = Column(String(50), nullable=True)
    error_code = Column(String(50), nullable=True)
    raw_response = Column(Text, nullable=True)

# Initialize DB
engine = create_engine('sqlite:///sip_monitor.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
