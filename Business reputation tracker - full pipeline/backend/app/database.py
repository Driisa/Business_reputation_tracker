from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    search_results = relationship("SearchResult", back_populates="company", cascade="all, delete-orphan")

class SearchResult(Base):
    __tablename__ = 'search_results'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id', ondelete='CASCADE'))
    query = Column(String(500))
    url = Column(String(1000))
    title = Column(String(500))
    snippet = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("Company", back_populates="search_results")
    scraped_content = relationship("ScrapedContent", back_populates="search_result", uselist=False, cascade="all, delete-orphan")

class ScrapedContent(Base):
    __tablename__ = 'scraped_content'
    
    id = Column(Integer, primary_key=True)
    search_result_id = Column(Integer, ForeignKey('search_results.id', ondelete='CASCADE'))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    search_result = relationship("SearchResult", back_populates="scraped_content")
    cleaned_content = relationship("CleanedContent", back_populates="scraped_content", uselist=False, cascade="all, delete-orphan")

class CleanedContent(Base):
    __tablename__ = 'cleaned_content'
    
    id = Column(Integer, primary_key=True)
    scraped_content_id = Column(Integer, ForeignKey('scraped_content.id', ondelete='CASCADE'))
    basic_cleaned_content = Column(Text)
    llm_cleaned_content = Column(Text)
    cleaning_metadata = Column(Text)  # JSON string containing entities, sentiment, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    scraped_content = relationship("ScrapedContent", back_populates="cleaned_content")
    sentiment_analysis = relationship("SentimentAnalysis", back_populates="cleaned_content", uselist=False, cascade="all, delete-orphan")

class SentimentAnalysis(Base):
    __tablename__ = 'sentiment_analysis'
    
    id = Column(Integer, primary_key=True)
    cleaned_content_id = Column(Integer, ForeignKey('cleaned_content.id', ondelete='CASCADE'))
    sentiment_score = Column(Integer)  # Score from -10 to 10
    sentiment_reason = Column(Text)  # Explanation of the sentiment score
    key_topics = Column(Text)  # JSON string containing identified topics
    reputation_impact = Column(Text)  # Assessment of impact on company reputation
    created_at = Column(DateTime, default=datetime.utcnow)
    cleaned_content = relationship("CleanedContent", back_populates="sentiment_analysis")

# Database setup
def init_db():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'Objekt storage.db'))
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

# Database session management
def get_db_session():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'Objekt storage.db'))
    Session = sessionmaker(bind=create_engine(f'sqlite:///{db_path}'))
    return Session() 