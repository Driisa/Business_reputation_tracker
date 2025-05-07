import os
import sys
import time
import logging
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.database import get_db_session
from backend.app.frontend_database import get_frontend_db_session, sync_to_frontend_db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), '..', 'data', 'frontend_sync.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_sync = None
        self.cooldown_period = 60  # Minimum seconds between syncs
        self.is_syncing = False
        
    def on_modified(self, event):
        if event.src_path.endswith('Objekt storage.db'):
            current_time = time.time()
            
            # Check if enough time has passed since last sync and not currently syncing
            if (self.last_sync is None or (current_time - self.last_sync) >= self.cooldown_period) and not self.is_syncing:
                logger.info("Database change detected. Starting sync...")
                self.is_syncing = True
                
                try:
                    # Get database sessions
                    main_db = get_db_session()
                    frontend_db = get_frontend_db_session()
                    
                    # Perform sync
                    success = sync_to_frontend_db(main_db, frontend_db)
                    
                    if success:
                        logger.info("Sync completed successfully")
                    else:
                        logger.error("Sync failed")
                    
                    # Update last sync time
                    self.last_sync = current_time
                    
                except SQLAlchemyError as e:
                    logger.error(f"Database error during sync: {str(e)}")
                except Exception as e:
                    logger.error(f"Unexpected error during sync: {str(e)}")
                finally:
                    # Close database sessions
                    try:
                        main_db.close()
                        frontend_db.close()
                    except Exception as e:
                        logger.error(f"Error closing database sessions: {str(e)}")
                    self.is_syncing = False

def perform_sync():
    """Perform a single sync operation."""
    logger.info("Performing manual sync...")
    try:
        main_db = get_db_session()
        frontend_db = get_frontend_db_session()
        success = sync_to_frontend_db(main_db, frontend_db)
        
        if success:
            logger.info("Manual sync completed successfully")
        else:
            logger.error("Manual sync failed")
            
    except Exception as e:
        logger.error(f"Error during manual sync: {str(e)}")
    finally:
        try:
            main_db.close()
            frontend_db.close()
        except Exception as e:
            logger.error(f"Error closing database sessions: {str(e)}")

def watch_database():
    """Start watching the database file for changes."""
    # Get the path to the database file
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    
    if not os.path.exists(db_path):
        logger.error(f"Database directory does not exist: {db_path}")
        return
    
    # Create event handler and observer
    event_handler = DatabaseChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, db_path, recursive=False)
    
    logger.info(f"Starting database watch on: {db_path}")
    logger.info("Press Ctrl+C to stop watching")
    
    try:
        # Start the observer
        observer.start()
        
        # Perform initial sync
        perform_sync()
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Stopping database watch...")
        observer.stop()
    except Exception as e:
        logger.error(f"Unexpected error in watch_database: {str(e)}")
        observer.stop()
    
    observer.join()

if __name__ == "__main__":
    try:
        watch_database()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1) 