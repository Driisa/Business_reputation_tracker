"""
SQLAlchemy models for the pipeline database.
Defines the database schema and relationships between different entities.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Float, JSON, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()

class SearchResult(Base):
    __tablename__ = "search_results"
    id                = Column(Integer, primary_key=True, index=True)
    company_id        = Column(String, index=True)
    company_name      = Column(String)
    title            = Column(String)
    link             = Column(String, unique=True, index=True)
    snippet          = Column(Text)
    published_date   = Column(Date)
    relevance_category = Column(String)
    relevance_score   = Column(Float)
    content_type     = Column(String)
    key_information  = Column(Text)
    reasoning        = Column(Text)
    raw_json         = Column(JSON)
    status           = Column(String, default="new")
    
    # Relationships
    scraped_contents = relationship("ScrapedContent", back_populates="search_result")

class ScrapedContent(Base):
    __tablename__ = "scraped_content"
    id               = Column(Integer, primary_key=True, index=True)
    search_result_id = Column(Integer, ForeignKey("search_results.id"), index=True)
    domain           = Column(String)
    scrape_time      = Column(DateTime(timezone=True), server_default=func.now())
    main_content     = Column(Text)
    status           = Column(String, default="new")
    
    # Relationships
    search_result = relationship("SearchResult", back_populates="scraped_contents")
    cleaned_contents = relationship("CleanedContent", back_populates="scraped_content")

class CleanedContent(Base):
    __tablename__ = "cleaned_content"
    id                  = Column(Integer, primary_key=True, index=True)
    scraped_content_id  = Column(Integer, ForeignKey("scraped_content.id"), index=True)
    cleaned_text        = Column(Text)
    word_count          = Column(Integer)
    status              = Column(String, default="new")
    
    # Relationships
    scraped_content = relationship("ScrapedContent", back_populates="cleaned_contents")
    analysis_results = relationship("AnalysisResult", back_populates="cleaned_content")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id                   = Column(Integer, primary_key=True, index=True)
    cleaned_content_id   = Column(Integer, ForeignKey("cleaned_content.id"), index=True)
    sentiment_score      = Column(Float)
    sentiment_label      = Column(String)
    analysis_text        = Column(Text)
    summary             = Column(Text)
    analysis_timestamp   = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    cleaned_content = relationship("CleanedContent", back_populates="analysis_results")
