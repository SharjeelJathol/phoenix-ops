from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from sqlalchemy import Text  # Add this import


Base = declarative_base()

class CommandLog(Base):
  __tablename__ = 'command_log'
  id = Column(Integer, primary_key=True)
  timestamp = Column(DateTime, default=datetime.datetime.utcnow)  # UTC standardization
  command = Column(String(50))
  user_id = Column(Integer)
  status = Column(String(20))  # Renamed from mock_status
  duration_ms = Column(Integer)  # New: Call duration in milliseconds
  trunk_id = Column(String(20))  # New: e.g., "Trunk_EU_01"
  error_code = Column(String(10), nullable=True)  # New: e.g., "408_TIMEOUT"
  raw_response = Column(Text, nullable=True)  # New: Full API/AMI response

# Initialize DB
engine = create_engine('sqlite:///sip_monitor.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)