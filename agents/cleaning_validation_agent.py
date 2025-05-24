import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import os
import logging
import argparse
from typing import Dict, List, Any, Optional
import html2text
from dotenv import load_dotenv
from tqdm import tqdm
from data.pipeline_db_config import SessionLocal
from data.pipeline_db_models import SearchResult, ScrapedContent, CleanedContent

# Setup argument parser
parser = argparse.ArgumentParser(description="Clean and validate scraped company content")
parser.add_argument("--min-words", type=int, default=50, help="Minimum word count threshold")
parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
args = parser.parse_args()

# Setup logging
log_level = logging.DEBUG if args.verbose else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("cleaning_validation_agent")

# Load environment variables (kept for potential future use)
load_dotenv()

# Constants
MIN_WORD_COUNT = args.min_words

class CleaningValidationAgent:
    def __init__(self, min_word_count=MIN_WORD_COUNT):
        """Initialize the cleaning and validation agent."""
        self.min_word_count = min_word_count
        self.session = SessionLocal()
        logger.debug(f"Initialized agent with minimum word count {min_word_count}")
    
    def _clean_html(self, content: str) -> str:
        """Clean HTML and extract readable text."""
        try:
            # Using html2text to convert HTML to plain text
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            converter.ignore_tables = False
            converter.body_width = 0  # No line wrapping
            
            # Clean the text
            cleaned_text = converter.handle(content).strip()
            
            # Additional cleaning steps
            # Remove excessive newlines
            import re
            cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
            
            return cleaned_text
        except Exception as e:
            logger.error(f"Failed to clean HTML: {e}")
            return content  # Return original content if cleaning fails
    
    def process_scraped_content(self):
        """Process all scraped content from the database using word count filter."""
        logger.info(f"Starting cleaning process with minimum word count {self.min_word_count}")
        
        try:
            # Get all scraped content that hasn't been processed yet
            scraped_contents = self.session.query(ScrapedContent).filter(
                ScrapedContent.status == "new"
            ).all()
            
            logger.info(f"Found {len(scraped_contents)} items to process")
            
            new_content_count = 0
            duplicate_content_count = 0
            too_short_count = 0
            
            # Process each item with a progress bar
            for scraped_content in tqdm(scraped_contents, desc="Processing content"):
                # Check if cleaned content already exists for this scraped content
                existing_cleaned = self.session.query(CleanedContent).filter(
                    CleanedContent.scraped_content_id == scraped_content.id
                ).first()
                
                if existing_cleaned:
                    duplicate_content_count += 1
                    logger.debug(f"Skipping duplicate cleaned content for scraped content ID {scraped_content.id}")
                    continue
                
                # Clean the content
                cleaned_text = self._clean_html(scraped_content.main_content)
                
                # Count words in the cleaned text
                word_count = len(cleaned_text.split())
                
                # Check if the content has enough words
                if word_count < self.min_word_count:
                    # Mark as too short and skip further processing
                    scraped_content.status = "too_short"
                    too_short_count += 1
                    try:
                        self.session.commit()
                        logger.info(f"Marked content ID {scraped_content.id} as too short ({word_count} words)")
                    except Exception as e:
                        logger.error(f"Error updating status: {e}")
                        self.session.rollback()
                    continue
                
                # If we reach here, the content has enough words (≥ min_word_count)
                # Create cleaned content record
                cleaned_content = CleanedContent(
                    scraped_content_id=scraped_content.id,
                    cleaned_text=cleaned_text,
                    word_count=word_count,
                    status="new"
                )
                
                # Add to session
                self.session.add(cleaned_content)
                new_content_count += 1
                
                # Update scraped content status
                scraped_content.status = "processed"
                
                # Commit after each successful processing
                try:
                    self.session.commit()
                    logger.info(f"Processed content ID {scraped_content.id} with {word_count} words")
                except Exception as e:
                    logger.error(f"Error saving to database: {e}")
                    self.session.rollback()
            
            logger.info("Cleaning process completed")
            logger.info(f"New cleaned content items: {new_content_count}")
            logger.info(f"Skipped duplicate content items: {duplicate_content_count}")
            logger.info(f"Content items marked as too short: {too_short_count}")
            
        except Exception as e:
            logger.error(f"An error occurred during processing: {e}")
            self.session.rollback()
        finally:
            self.session.close()

def main():
    """Main function to run the agent."""
    try:
        agent = CleaningValidationAgent(min_word_count=MIN_WORD_COUNT)
        agent.process_scraped_content()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()