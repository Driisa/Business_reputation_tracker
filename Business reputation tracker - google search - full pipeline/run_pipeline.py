#!/usr/bin/env python3
import os
import time
from datetime import datetime
from data.pipeline_db_config import init_db, SessionLocal
from data.pipeline_db_models import SearchResult, ScrapedContent, CleanedContent, AnalysisResult
from sqlalchemy import and_
from logging_config import setup_logging

# Setup logging
loggers = setup_logging()
logger = loggers["pipeline"]
db_logger = loggers["database"]

def check_for_duplicate_search_result(session, link):
    """Check if a search result with the given link already exists."""
    try:
        result = session.query(SearchResult).filter(SearchResult.link == link).first() is not None
        db_logger.debug(f"Checked for duplicate search result: {link}")
        return result
    except Exception as e:
        db_logger.error(f"Error checking for duplicate search result: {str(e)}")
        raise

def check_for_duplicate_scraped_content(session, search_result_id):
    """Check if scraped content for the given search result already exists."""
    return session.query(ScrapedContent).filter(ScrapedContent.search_result_id == search_result_id).first() is not None

def check_for_duplicate_cleaned_content(session, scraped_content_id):
    """Check if cleaned content for the given scraped content already exists."""
    return session.query(CleanedContent).filter(CleanedContent.scraped_content_id == scraped_content_id).first() is not None

def check_for_duplicate_analysis(session, cleaned_content_id):
    """Check if analysis for the given cleaned content already exists."""
    return session.query(AnalysisResult).filter(AnalysisResult.cleaned_content_id == cleaned_content_id).first() is not None

def check_database_state():
    """Check the current state of the database."""
    session = SessionLocal()
    try:
        search_results = session.query(SearchResult).count()
        scraped_content = session.query(ScrapedContent).count()
        cleaned_content = session.query(CleanedContent).count()
        analysis_results = session.query(AnalysisResult).count()
        
        db_logger.info("Current database state:")
        db_logger.info(f"- Search Results: {search_results}")
        db_logger.info(f"- Scraped Content: {scraped_content}")
        db_logger.info(f"- Cleaned Content: {cleaned_content}")
        db_logger.info(f"- Analysis Results: {analysis_results}")
        
        return {
            "search_results": search_results,
            "scraped_content": scraped_content,
            "cleaned_content": cleaned_content,
            "analysis_results": analysis_results
        }
    except Exception as e:
        db_logger.error(f"Error checking database state: {str(e)}")
        raise
    finally:
        session.close()

def run_pipeline():
    """Run the complete pipeline."""
    start_time = time.time()
    logger.info("Starting pipeline run...")
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        db_logger.info("Database initialized successfully")
    except Exception as e:
        db_logger.error(f"Failed to initialize database: {str(e)}")
        raise
    
    # Check initial state
    initial_state = check_database_state()
    
    try:
        # 1. Run intelligent search
        logger.info("\n=== Step 1: Running Intelligent Search ===")
        search_logger = loggers["search"]
        search_logger.info("Starting intelligent search process")
        os.system("python agents/intelligent_search_agent.py")
        
        # Check state after search
        search_state = check_database_state()
        if search_state["search_results"] <= initial_state["search_results"]:
            search_logger.warning("No new search results found. This might be normal if all results are duplicates.")
        else:
            search_logger.info(f"Found {search_state['search_results'] - initial_state['search_results']} new search results")
        
        # 2. Run web scraping
        logger.info("\n=== Step 2: Running Web Scraping ===")
        scraping_logger = loggers["scraping"]
        scraping_logger.info("Starting web scraping process")
        os.system("python agents/web_scraping_agent.py")
        
        # Check state after scraping
        scrape_state = check_database_state()
        if scrape_state["scraped_content"] <= initial_state["scraped_content"]:
            scraping_logger.warning("No new scraped content found. This might be normal if all content was already scraped.")
        else:
            scraping_logger.info(f"Found {scrape_state['scraped_content'] - initial_state['scraped_content']} new scraped content")
        
        # 3. Run cleaning and validation
        logger.info("\n=== Step 3: Running Cleaning and Validation ===")
        cleaning_logger = loggers["cleaning"]
        cleaning_logger.info("Starting cleaning and validation process")
        os.system("python agents/cleaning_validation_agent.py")
        
        # Check state after cleaning
        clean_state = check_database_state()
        if clean_state["cleaned_content"] <= initial_state["cleaned_content"]:
            cleaning_logger.warning("No new cleaned content found. This might be normal if all content was already cleaned.")
        else:
            cleaning_logger.info(f"Found {clean_state['cleaned_content'] - initial_state['cleaned_content']} new cleaned content")
        
        # 4. Run analysis
        logger.info("\n=== Step 4: Running Analysis ===")
        analysis_logger = loggers["analysis"]
        analysis_logger.info("Starting analysis process")
        os.system("python agents/analyst_agent.py")
        
        # Check final state
        final_state = check_database_state()
        
        # Calculate pipeline statistics
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info("\n=== Pipeline Statistics ===")
        logger.info(f"Total duration: {duration:.2f} seconds")
        logger.info(f"New search results: {final_state['search_results'] - initial_state['search_results']}")
        logger.info(f"New scraped content: {final_state['scraped_content'] - initial_state['scraped_content']}")
        logger.info(f"New cleaned content: {final_state['cleaned_content'] - initial_state['cleaned_content']}")
        logger.info(f"New analysis results: {final_state['analysis_results'] - initial_state['analysis_results']}")
        
        logger.info("\nPipeline completed successfully!")
        
    except Exception as e:
        logger.error(f"Pipeline failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    run_pipeline() 