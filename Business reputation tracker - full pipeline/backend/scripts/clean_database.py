import os
import sys
import logging
from datetime import datetime

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from backend.app.database import Base as MainBase, init_db
from backend.app.frontend_database import Base as FrontendBase, init_frontend_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), '..', 'data', f'clean_database_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')),
        logging.StreamHandler()
    ]
)

def clean_database(db_path, base_class, init_func, db_name):
    """Drop all tables and reinitialize a specific database."""
    engine = create_engine(f'sqlite:///{db_path}')
    
    try:
        # Drop all tables
        with engine.connect() as connection:
            # Get all table names
            result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            
            # Drop each table
            for table in tables:
                connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
                logging.info(f"Dropped table from {db_name}: {table}")
            
            connection.commit()
            logging.info(f"\nAll tables dropped successfully from {db_name}")
        
        # Reinitialize database with correct schema
        logging.info(f"\nReinitializing {db_name}...")
        init_func()
        logging.info(f"{db_name} reinitialized successfully!")
        
        return True
        
    except Exception as e:
        logging.error(f"Error cleaning {db_name}: {str(e)}")
        return False

def clean_all_databases():
    """Clean and reinitialize both main and frontend databases."""
    try:
        # Clean main database
        main_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'Objekt storage.db'))
        if not clean_database(main_db_path, MainBase, init_db, "Main Database"):
            raise Exception("Failed to clean main database")
        
        # Clean frontend database
        frontend_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'frontend_data.db'))
        if not clean_database(frontend_db_path, FrontendBase, init_frontend_db, "Frontend Database"):
            raise Exception("Failed to clean frontend database")
        
        logging.info("\nBoth databases cleaned and reinitialized successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Error in clean_all_databases: {str(e)}")
        return False

if __name__ == "__main__":
    if clean_all_databases():
        sys.exit(0)
    else:
        sys.exit(1) 