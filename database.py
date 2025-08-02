from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from sqlalchemy import Text

Base = declarative_base()

class CommandLog(Base):
    __tablename__ = 'command_log'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    command = Column(String(50))
    user_id = Column(Integer)
    # Corrected: Increased user_role length to accommodate multiple roles as a string
    user_role = Column(String(50))
    status = Column(String(20))
    duration_ms = Column(Integer, nullable=True) # Added nullable=True
    trunk_id = Column(String(50), nullable=True) # Increased length and added nullable=True
    error_code = Column(String(50), nullable=True) # Increased length and added nullable=True
    raw_response = Column(Text, nullable=True)

# Initialize DB
engine = create_engine('sqlite:///sip_monitor.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
