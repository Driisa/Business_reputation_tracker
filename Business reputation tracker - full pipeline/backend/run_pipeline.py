from backend.app.database import init_db
from backend.agents.company_search_agent import CompanySearchAgent
from backend.agents.web_scraping_agent import ContentScraper
from backend.agents.LLM_cleaning_agent import ContentCleaner
from backend.agents.LLM_sentiment_agent import SentimentAnalyzer
from backend.app.frontend_database import init_frontend_db, verify_databases
from backend.app.sync_frontend_data import perform_sync
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import sys
import threading
import os
import json

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging
def setup_logging():
    """Configure logging with rotation and different handlers."""
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(message)s'  # Simplified console format
    )

    # Create handlers
    # Main pipeline log file (rotates when reaches 5MB, keeps 5 backup files)
    pipeline_handler = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, 'pipeline.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    pipeline_handler.setFormatter(file_formatter)
    pipeline_handler.setLevel(logging.INFO)

    # Error log file (only errors and above)
    error_handler = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, 'error.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)

    # Content cleaner specific log file
    cleaner_handler = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, 'content_cleaner.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    cleaner_handler.setFormatter(file_formatter)
    cleaner_handler.setLevel(logging.INFO)

    # Console handler with higher level to reduce noise
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors in console

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(pipeline_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    # Create separate loggers for different components
    loggers = {
        'pipeline': logging.getLogger('pipeline'),
        'search': logging.getLogger('search'),
        'scraper': logging.getLogger('scraper'),
        'cleaner': logging.getLogger('cleaner'),
        'analyzer': logging.getLogger('analyzer'),
        'database': logging.getLogger('database')
    }

    # Add specific handlers to component loggers
    loggers['cleaner'].addHandler(cleaner_handler)
    loggers['cleaner'].setLevel(logging.INFO)

    # Set console level to WARNING for all component loggers
    for logger in loggers.values():
        logger.setLevel(logging.WARNING)

    return loggers

# Initialize logging
loggers = setup_logging()
logger = loggers['pipeline']

def log_pipeline_event(event_type, data=None):
    """Log pipeline events in a structured format."""
    event = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'data': data or {}
    }
    
    # Only log specific events to console
    if event_type in ['pipeline_start', 'pipeline_complete', 'pipeline_error']:
        logger.info(f"Pipeline {event_type.split('_')[1]}: {data or ''}")
    elif event_type in ['search_complete', 'scrape_complete', 'clean_complete', 'analyze_complete']:
        results_count = data.get('results_count', 0) if data else 0
        logger.info(f"{event_type.split('_')[0].title()} completed: {results_count} results")
    
    # Always log to file
    logger.info(json.dumps(event))

def initialize_databases():
    """Initialize and verify both databases."""
    try:
        logging.info("Initializing databases...")
        init_frontend_db()  # This will also initialize the main database
        
        # Verify both databases are accessible
        if not verify_databases():
            raise Exception("Database verification failed")
        
        logging.info("Both databases initialized and verified successfully")
        return True
    except Exception as e:
        logging.error(f"Database initialization failed: {str(e)}")
        return False

def run_pipeline():
    """Run the complete pipeline of agents with improved error handling and logging."""
    start_time = time.time()
    
    try:
        # Initialize databases
        log_pipeline_event('pipeline_start')
        logger.info("Initializing databases...")
        if not initialize_databases():
            raise Exception("Database initialization failed")
        
        # Step 1: Search for companies
        log_pipeline_event('search_start')
        logger.info("=== Starting Search Agent ===")
        search_agent = CompanySearchAgent()
        search_results = search_agent.search_companies()
        
        if not search_results or not isinstance(search_results, dict):
            logger.warning("Search agent returned no results or invalid format")
            search_results = {'results_count': 0}
        else:
            search_results.setdefault('results_count', 0)
        
        log_pipeline_event('search_complete', {'results_count': search_results['results_count']})
        
        if search_results['results_count'] == 0:
            logger.warning("No search results found. Pipeline may not proceed as expected.")
        
        # Step 2: Scrape content
        log_pipeline_event('scrape_start')
        logger.info("=== Starting Scraping Agent ===")
        scraper = ContentScraper()
        scraped_content = scraper.scrape_all_urls()
        
        if not scraped_content or not isinstance(scraped_content, dict):
            logger.warning("Scraper returned no results or invalid format")
            scraped_content = {'results_count': 0}
        else:
            scraped_content.setdefault('results_count', 0)
        
        log_pipeline_event('scrape_complete', {'results_count': scraped_content['results_count']})
        
        if scraped_content['results_count'] == 0:
            logger.warning("No content was scraped. Pipeline may not proceed as expected.")
        
        # Step 3: Clean content
        log_pipeline_event('clean_start')
        logger.info("=== Starting LLM Cleaning Agent ===")
        cleaner = ContentCleaner()
        # Log to content_cleaner.log
        loggers['cleaner'].info("Starting content cleaning process")
        cleaned_content = cleaner.clean_all_content()
        
        if not cleaned_content or not isinstance(cleaned_content, dict):
            logger.warning("Cleaner returned no results or invalid format")
            loggers['cleaner'].warning("Cleaner returned no results or invalid format")
            cleaned_content = {'results_count': 0}
        else:
            cleaned_content.setdefault('results_count', 0)
        
        log_pipeline_event('clean_complete', {'results_count': cleaned_content['results_count']})
        loggers['cleaner'].info(f"Content cleaning completed. Processed {cleaned_content['results_count']} articles.")
        
        if cleaned_content['results_count'] == 0:
            logger.warning("No content was cleaned. Pipeline may not proceed as expected.")
            loggers['cleaner'].warning("No content was cleaned. Pipeline may not proceed as expected.")
        
        # Step 4: Analyze sentiment
        log_pipeline_event('analyze_start')
        logger.info("=== Starting LLM sentiment Agent ===")
        analyzer = SentimentAnalyzer()
        analysis_results = analyzer.analyze_all_content()
        
        if not analysis_results or not isinstance(analysis_results, dict):
            logger.warning("Analyzer returned no results or invalid format")
            analysis_results = {'results_count': 0}
        else:
            analysis_results.setdefault('results_count', 0)
        
        log_pipeline_event('analyze_complete', {'results_count': analysis_results['results_count']})
        
        if analysis_results['results_count'] == 0:
            logger.warning("No content was analyzed. Pipeline may not proceed as expected.")
        
        # Step 5: Sync to Frontend Database
        log_pipeline_event('sync_start')
        logger.info("=== Syncing to Frontend Database ===")
        sync_result = perform_sync()
        if sync_result is False:
            raise Exception("Frontend database sync failed")
        log_pipeline_event('sync_complete')
        
        # Verify databases after sync
        if not verify_databases():
            raise Exception("Database verification failed after sync")
        
        # Calculate and log execution time
        execution_time = time.time() - start_time
        log_pipeline_event('pipeline_complete', {
            'execution_time': execution_time,
            'search_results': search_results.get('results_count', 0),
            'scraped_content': scraped_content.get('results_count', 0),
            'cleaned_content': cleaned_content.get('results_count', 0),
            'analyzed_content': analysis_results.get('results_count', 0)
        })
        
        return {
            'status': 'success',
            'execution_time': execution_time,
            'search_results': search_results.get('results_count', 0),
            'scraped_content': scraped_content.get('results_count', 0),
            'cleaned_content': cleaned_content.get('results_count', 0),
            'analyzed_content': analysis_results.get('results_count', 0)
        }
        
    except Exception as e:
        log_pipeline_event('pipeline_error', {'error': str(e)})
        logger.error(f"Pipeline failed with error: {str(e)}", exc_info=True)
        if 'cleaner' in loggers:
            loggers['cleaner'].error(f"Content cleaning failed with error: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'execution_time': time.time() - start_time
        }

def start_sync_watcher():
    """Start the database sync watcher in a separate thread."""
    from backend.app.sync_frontend_data import watch_database
    sync_thread = threading.Thread(target=watch_database, daemon=True)
    sync_thread.start()
    return sync_thread

if __name__ == "__main__":
    try:
        # Start the sync watcher
        sync_thread = start_sync_watcher()
        
        # Run the pipeline
        result = run_pipeline()
        
        if result['status'] == 'error':
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}")
        sys.exit(1) 