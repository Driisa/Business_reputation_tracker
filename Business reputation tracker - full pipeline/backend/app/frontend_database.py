from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os
import json
import logging
from sqlalchemy.sql import text

# Import main database models and functions
from .database import (
    Company, SearchResult, ScrapedContent, CleanedContent, 
    SentimentAnalysis, init_db, get_db_session
)

Base = declarative_base()

# Set up logging
logger = logging.getLogger(__name__)

class CompanyFrontend(Base):
    __tablename__ = 'companies_frontend'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(Text)
    overall_sentiment_score = Column(Float)  # Average sentiment score
    sentiment_trend = Column(JSON)  # Historical sentiment scores
    key_topics = Column(JSON)  # Aggregated topics with frequency
    reputation_summary = Column(Text)  # Overall reputation assessment
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    articles = relationship("ArticleFrontend", back_populates="company", cascade="all, delete-orphan")

class ArticleFrontend(Base):
    __tablename__ = 'articles_frontend'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies_frontend.id', ondelete='CASCADE'))
    title = Column(String(500))
    url = Column(String(1000))
    published_date = Column(DateTime)
    sentiment_score = Column(Integer)  # -10 to 10
    sentiment_reason = Column(Text)
    key_topics = Column(JSON)  # List of topics
    reputation_impact = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("CompanyFrontend", back_populates="articles")

class TopicInsight(Base):
    __tablename__ = 'topic_insights'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies_frontend.id', ondelete='CASCADE'))
    topic = Column(String(200))
    sentiment_score = Column(Float)  # Average sentiment for this topic
    frequency = Column(Integer)  # How often this topic appears
    last_mentioned = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("CompanyFrontend")

def verify_databases():
    """Verify that both databases are properly initialized and accessible."""
    main_db = None
    frontend_db = None
    
    try:
        # Check main database
        main_db = get_db_session()
        main_db.execute(text("SELECT 1"))
        
        # Check frontend database
        frontend_db = get_frontend_db_session()
        frontend_db.execute(text("SELECT 1"))
        
        logger.info("Database verification successful")
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Database verification failed: {str(e)}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error during database verification: {str(e)}")
        return False
        
    finally:
        # Clean up database sessions
        try:
            if main_db:
                main_db.close()
            if frontend_db:
                frontend_db.close()
        except Exception as e:
            logger.error(f"Error closing database sessions: {str(e)}")

def init_frontend_db():
    """Initialize the frontend database and verify both databases."""
    try:
        # First ensure main database is initialized
        init_db()
        
        # Initialize frontend database
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'frontend_data.db'))
        engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(engine)
        
        # Verify both databases
        if not verify_databases():
            raise Exception("Database verification failed after initialization")
        
        logger.info("Both databases initialized and verified successfully")
        return sessionmaker(bind=engine)()
        
    except Exception as e:
        logger.error(f"Error initializing databases: {str(e)}")
        raise

def get_frontend_db_session():
    """Get a database session for the frontend database."""
    try:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'frontend_data.db'))
        Session = sessionmaker(bind=create_engine(f'sqlite:///{db_path}'))
        return Session()
    except Exception as e:
        logger.error(f"Error getting frontend database session: {str(e)}")
        raise

def sync_to_frontend_db(main_db_session, frontend_db_session):
    """
    Sync data from the main database to the frontend database.
    This function should be called periodically to keep the frontend data up to date.
    """
    try:
        # Verify both databases are accessible
        if not verify_databases():
            raise Exception("Database verification failed before sync")
        
        # Get all companies from main database
        main_companies = main_db_session.query(Company).all()
        main_company_names = {company.name for company in main_companies}
        
        # Get all companies from frontend database
        frontend_companies = frontend_db_session.query(CompanyFrontend).all()
        
        # Remove companies that no longer exist in main database
        for frontend_company in frontend_companies:
            if frontend_company.name not in main_company_names:
                frontend_db_session.delete(frontend_company)
                logger.info(f"Removed company from frontend database: {frontend_company.name}")
        
        # Process remaining companies
        for company in main_companies:
            # Create or update company in frontend database
            frontend_company = frontend_db_session.query(CompanyFrontend).filter_by(name=company.name).first()
            if not frontend_company:
                frontend_company = CompanyFrontend(name=company.name, description=company.description)
                frontend_db_session.add(frontend_company)
            
            # Get all sentiment analyses for this company
            sentiment_analyses = (
                main_db_session.query(SentimentAnalysis)
                .join(CleanedContent)
                .join(ScrapedContent)
                .join(SearchResult)
                .filter(SearchResult.company_id == company.id)
                .all()
            )
            
            # Calculate overall sentiment score
            if sentiment_analyses:
                overall_score = sum(analysis.sentiment_score for analysis in sentiment_analyses) / len(sentiment_analyses)
                frontend_company.overall_sentiment_score = overall_score
            
            # Aggregate topics
            all_topics = []
            for analysis in sentiment_analyses:
                try:
                    topics = json.loads(analysis.key_topics) if analysis.key_topics else []
                    all_topics.extend(topics)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in key_topics for analysis {analysis.id}")
                    continue
            
            # Count topic frequencies
            topic_freq = {}
            for topic in all_topics:
                topic_freq[topic] = topic_freq.get(topic, 0) + 1
            
            frontend_company.key_topics = json.dumps(topic_freq)
            
            # Get all URLs from main database for this company
            main_urls = set()
            for analysis in sentiment_analyses:
                search_result = (
                    main_db_session.query(SearchResult)
                    .join(ScrapedContent)
                    .join(CleanedContent)
                    .filter(CleanedContent.id == analysis.cleaned_content_id)
                    .first()
                )
                if search_result:
                    main_urls.add(search_result.url)
            
            # Remove articles that no longer exist in main database
            existing_articles = frontend_db_session.query(ArticleFrontend).filter_by(company_id=frontend_company.id).all()
            for article in existing_articles:
                if article.url not in main_urls:
                    frontend_db_session.delete(article)
                    logger.info(f"Removed article from frontend database: {article.url}")
            
            # Create or update articles
            for analysis in sentiment_analyses:
                search_result = (
                    main_db_session.query(SearchResult)
                    .join(ScrapedContent)
                    .join(CleanedContent)
                    .filter(CleanedContent.id == analysis.cleaned_content_id)
                    .first()
                )
                
                if search_result:
                    article = frontend_db_session.query(ArticleFrontend).filter_by(url=search_result.url).first()
                    if not article:
                        article = ArticleFrontend(
                            company=frontend_company,
                            title=search_result.title,
                            url=search_result.url,
                            published_date=search_result.created_at,
                            sentiment_score=analysis.sentiment_score,
                            sentiment_reason=analysis.sentiment_reason,
                            key_topics=analysis.key_topics,
                            reputation_impact=analysis.reputation_impact
                        )
                        frontend_db_session.add(article)
                    else:
                        # Update existing article
                        article.title = search_result.title
                        article.published_date = search_result.created_at
                        article.sentiment_score = analysis.sentiment_score
                        article.sentiment_reason = analysis.sentiment_reason
                        article.key_topics = analysis.key_topics
                        article.reputation_impact = analysis.reputation_impact
            
            # Remove topic insights that no longer exist
            existing_topics = set(topic_freq.keys())
            existing_insights = frontend_db_session.query(TopicInsight).filter_by(company_id=frontend_company.id).all()
            for insight in existing_insights:
                if insight.topic not in existing_topics:
                    frontend_db_session.delete(insight)
                    logger.info(f"Removed topic insight from frontend database: {insight.topic}")
            
            # Create or update topic insights
            for topic, freq in topic_freq.items():
                topic_sentiments = [
                    analysis.sentiment_score
                    for analysis in sentiment_analyses
                    if topic in json.loads(analysis.key_topics or '[]')
                ]
                
                if topic_sentiments:
                    avg_sentiment = sum(topic_sentiments) / len(topic_sentiments)
                    insight = frontend_db_session.query(TopicInsight).filter_by(
                        company_id=frontend_company.id,
                        topic=topic
                    ).first()
                    
                    if not insight:
                        insight = TopicInsight(
                            company_id=frontend_company.id,
                            topic=topic,
                            sentiment_score=avg_sentiment,
                            frequency=freq,
                            last_mentioned=datetime.utcnow()
                        )
                        frontend_db_session.add(insight)
                    else:
                        insight.sentiment_score = avg_sentiment
                        insight.frequency = freq
                        insight.last_mentioned = datetime.utcnow()
        
        frontend_db_session.commit()
        logger.info("Database sync completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error syncing to frontend database: {str(e)}")
        frontend_db_session.rollback()
        return False 