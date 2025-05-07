import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
import os
from openai import OpenAI
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("content_cleaner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ContentCleaner:
    def __init__(self):
        """Initialize the content cleaner with OpenAI client."""
        # Load environment variables
        load_dotenv()
        api_key = os.getenv("1OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        
        # Initialize metrics
        self.metrics = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'processing_time': 0
        }

    def clean_content(self, content):
        """Clean a single piece of content using basic cleaning and LLM processing."""
        try:
            # Basic cleaning
            cleaned_content = self._basic_cleaning(content)
            
            # LLM cleaning
            llm_cleaned = self._llm_cleaning(cleaned_content)
            
            return {
                'basic_cleaned_content': cleaned_content,
                'llm_cleaned_content': llm_cleaned,
                'cleaning_timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error cleaning content: {str(e)}")
            return None

    def _basic_cleaning(self, content):
        """Perform basic text cleaning."""
        if not content:
            return ""
        
        try:
            # Remove HTML tags
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Remove URLs but keep the context
            text = re.sub(r'https?://\S+', '[URL]', text)
            
            # Normalize quotation marks
            text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
            
            # Fix sentence boundaries
            text = re.sub(r'([.!?])\s*([A-Z])', r'\1\n\2', text)
            
            # Remove multiple newlines
            text = re.sub(r'\n\s*\n', '\n\n', text)
            
            return text.strip()
        except Exception as e:
            logger.error(f"Error in basic cleaning: {str(e)}")
            return content

    def _llm_cleaning(self, content):
        """Clean content using LLM to focus on company-related information."""
        try:
            system_message = """You are a content cleaning expert. Your task is to clean and structure the content to focus on company-related information, removing irrelevant content and maintaining the key messages about the company's reputation, customer feedback, corporate responsibility, and news.

            Guidelines:
            1. Keep only content directly related to the company
            2. Remove job postings, advertisements, and irrelevant content
            3. Preserve customer reviews, news, and corporate information
            4. Maintain the original sentiment and key messages
            5. Structure the content in a clear, readable format
            6. Remove duplicate information
            7. Keep dates and timestamps when relevant"""

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": content}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in LLM cleaning: {str(e)}")
            return content

    def process_file(self, input_file, output_file):
        """Process the input JSON file and save cleaned content to output file."""
        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Process each result
            for result in data['results']:
                self.metrics['total_processed'] += 1
                
                # Clean the content
                cleaned = self.clean_content(result['content'])
                
                if cleaned:
                    # Add cleaned content to the result
                    result['cleaned_content'] = cleaned
                    self.metrics['successful'] += 1
                else:
                    self.metrics['failed'] += 1
            
            # Save to output file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Processing completed. Successful: {self.metrics['successful']}, Failed: {self.metrics['failed']}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return False

def main():
    """Run the content cleaner"""
    input_file = "web_scraping_agent\scraped_content.json"
    output_file = "cleaned_content.json"
    
    cleaner = ContentCleaner()
    success = cleaner.process_file(input_file, output_file)
    
    if success:
        logger.info("Content cleaning completed successfully")
    else:
        logger.error("Content cleaning failed")

if __name__ == "__main__":
    main()