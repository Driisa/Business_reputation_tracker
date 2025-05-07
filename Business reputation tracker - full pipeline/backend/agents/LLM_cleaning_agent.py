import re
import asyncio
import time
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys
import os
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
import logging

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.database import ScrapedContent, CleanedContent, get_db_session

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
    def __init__(self, config=None):
        """Initialize the content cleaner with database session and OpenAI client."""
        # Default configuration with cost-saving options
        self.default_config = {
            'basic_cleaning': True,
            'detect_content_type': True,
            'coreference_resolution': False,  # Turn off by default to save costs
            'segment_content': True,
            'llm_cleaning': True,
            'async_processing': True,
            'batch_size': 10,          # Increased batch size for efficiency
            'llm_model': "gpt-4.1-nano",  # Use cheaper model
            'validation': True
        }
        
        # Use provided config or default
        self.config = config or self.default_config
        
        # Initialize database session
        self.db = get_db_session()
        
        # Load environment and initialize OpenAI clients
        load_dotenv()
        api_key = os.getenv("1OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        
        # Initialize metrics
        self.metrics = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'processing_time': 0,
            'avg_content_length_reduction': 0,
            'validation_issues': {}
        }
    
    async def clean_all_content_async(self):
        """Clean all scraped content asynchronously in batches."""
        # Get all scraped content that doesn't have cleaned content
        scraped_contents = self.db.query(ScrapedContent).outerjoin(
            CleanedContent
        ).filter(CleanedContent.id == None).all()
        
        total_count = len(scraped_contents)
        logger.info(f"Found {total_count} articles to clean")
        
        # Process in batches
        batch_size = self.config.get('batch_size', 10)
        batches = [scraped_contents[i:i + batch_size] for i in range(0, total_count, batch_size)]
        
        start_time = time.time()
        
        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")
            
            # Process the batch concurrently
            tasks = [self.process_content_async(content) for content in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Save results to database
            for content, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing content ID {content.id}: {str(result)}")
                    self.metrics['failed'] += 1
                    continue
                
                try:
                    # Create the cleaned content entry
                    cleaned_content = CleanedContent(
                        scraped_content_id=content.id,
                        basic_cleaned_content=result.get('basic_cleaned_content', ''),
                        llm_cleaned_content=result.get('cleaned_content', ''),
                        cleaning_metadata=json.dumps(result.get('metadata', {}))
                    )
                    
                    self.db.add(cleaned_content)
                    self.db.commit()
                    
                    self.metrics['successful'] += 1
                except Exception as e:
                    logger.error(f"Error saving cleaned content ID {content.id}: {str(e)}")
                    self.db.rollback()
                    self.metrics['failed'] += 1
            
            # Update metrics
            self.metrics['total_processed'] = self.metrics['successful'] + self.metrics['failed']
            
            # Log progress
            progress = (batch_idx + 1) / len(batches) * 100
            logger.info(f"Progress: {progress:.2f}% ({self.metrics['successful']}/{total_count} successful)")
        
        # Calculate total processing time
        self.metrics['processing_time'] = time.time() - start_time
        logger.info(f"Content cleaning completed in {self.metrics['processing_time']:.2f} seconds")
        
        return self._get_all_cleaning_results()
    
    def clean_all_content(self):
        """Clean all scraped content."""
        if self.config.get('async_processing', True):
            # Run the async method in an event loop
            return asyncio.run(self.clean_all_content_async())
        
        # Synchronous implementation omitted for brevity
        # Would be similar to async but sequential
        return {'results_count': 0, 'metrics': self.metrics, 'contents': []}
    
    async def process_content_async(self, scraped_content):
        """Process content through the cleaning pipeline asynchronously."""
        try:
            content = scraped_content.content
            if not content:
                return {
                    'cleaned_content': '',
                    'basic_cleaned_content': '',
                    'metadata': {'error': 'Empty content'}
                }
            
            metadata = {'original_length': len(content)}
            initial_length = len(content)
            
            # Apply basic cleaning
            if self.config.get('basic_cleaning', True):
                try:
                    content = self._basic_cleaning(content)
                    metadata['after_basic_cleaning_length'] = len(content)
                    basic_cleaned_content = content
                except Exception as e:
                    logger.error(f"Error in basic cleaning: {str(e)}")
                    basic_cleaned_content = content
            else:
                basic_cleaned_content = content
            
            # Detect content type and preprocess (simplified)
            if self.config.get('detect_content_type', True):
                try:
                    content_type = self._simple_content_type_detection(content)
                    metadata['content_type'] = content_type
                except Exception as e:
                    logger.error(f"Error in content type detection: {str(e)}")
                    metadata['content_type'] = 'article'
            
            # Segment content (simple implementation)
            if self.config.get('segment_content', True):
                try:
                    paragraphs = re.split(r'\n\s*\n', content)
                    paragraphs = [p.strip() for p in paragraphs if p.strip()]
                    content = '\n\n'.join(paragraphs)
                    metadata['segments_count'] = len(paragraphs)
                except Exception as e:
                    logger.error(f"Error in content segmentation: {str(e)}")
            
            # Combined LLM cleaning that handles all operations in one call to save costs
            if self.config.get('llm_cleaning', True):
                try:
                    result = await self._single_pass_llm_processing(content)
                    content = result['cleaned_content']
                    metadata.update(result['metadata'])
                except Exception as e:
                    logger.error(f"Error in LLM processing: {str(e)}")
                    # Continue with current content
            
            # Simple validation
            if self.config.get('validation', True):
                try:
                    validation = self._simple_validation(content, metadata)
                    metadata['validation'] = validation
                    if validation.get('issues'):
                        for issue in validation['issues']:
                            self.metrics['validation_issues'][issue] = self.metrics['validation_issues'].get(issue, 0) + 1
                except Exception as e:
                    logger.error(f"Error in validation: {str(e)}")
            
            # Calculate length reduction
            final_length = len(content)
            length_reduction_percent = ((initial_length - final_length) / initial_length) * 100 if initial_length > 0 else 0
            metadata['length_reduction_percent'] = length_reduction_percent
            
            # Update average length reduction metric
            current_avg = self.metrics.get('avg_content_length_reduction', 0)
            self.metrics['avg_content_length_reduction'] = (
                (current_avg * self.metrics['successful'] + length_reduction_percent) /
                (self.metrics['successful'] + 1) if self.metrics['successful'] > 0 else length_reduction_percent
            )
            
            return {
                'cleaned_content': content,
                'basic_cleaned_content': basic_cleaned_content,
                'metadata': metadata
            }
        except Exception as e:
            logger.error(f"Error in process_content_async: {str(e)}")
            raise
    
    def _basic_cleaning(self, content):
        """Perform basic text cleaning for sentiment analysis."""
        if not content:
            return ""
        
        try:
            # Remove HTML tags
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Fix common OCR issues but preserve sentiment indicators
            text = text.replace('|', 'I').replace('l', 'I')
            
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
            if isinstance(content, str):
                return re.sub(r'\s+', ' ', content).strip()
            return ""
    
    def _simple_content_type_detection(self, content):
        """Simplified content type detection to reduce processing cost."""
        try:
            content_lower = content.lower()
            
            # Check for basic indicators with minimal regex
            if content.count('<table') > 2 or content.count('|') > 8:
                return 'tabular'
            
            if 'press release' in content_lower or 'for immediate release' in content_lower:
                return 'press_release'
            
            if any(term in content_lower for term in ['review', 'rating', 'stars']):
                return 'review'
            
            if re.search(r'by\s+[\w\s\.]+', content_lower) and any(term in content_lower for term in ['reporter', 'journalist', 'editor']):
                return 'news_article'
            
            if any(term in content_lower for term in ['blog', 'posted on', 'published on']):
                return 'blog_post'
            
            if '@' in content or '#' in content:
                return 'social_media'
            
            # Default to article
            return 'article'
        except Exception as e:
            logger.error(f"Error in content type detection: {str(e)}")
            return 'article'
    
    async def _single_pass_llm_processing(self, content):
        """
        Combined LLM processing that handles cleaning, entity extraction, 
        sentiment analysis, and summary in one call to save costs.
        """
        if not content:
            return {
                'cleaned_content': '',
                'metadata': {}
            }
        
        logger.info("Starting single-pass LLM processing...")
        
        try:
            # Create a comprehensive system message that covers all needed operations
            system_message = """You are a company reputation and sentiment analysis expert. Your task is to clean, structure, and analyze the sentiment of content specifically related to the target company.
            
            Return your response as a JSON object with the following structure:
            {
                "cleaned_content": "The cleaned and structured text content, focusing only on parts relevant to the target company",
                "entities": ["List of relevant entities (company name, products, key people, subsidiaries) that are directly related to the target company"],
                "sentiment_analysis": {
                    "overall_sentiment": "positive/negative/neutral/mixed",
                    "confidence": 0.0 to 1.0,
                    "key_positive_points": ["list of main positive points about the company"],
                    "key_negative_points": ["list of main negative points about the company"],
                    "key_entity_sentiments": [
                        {
                            "entity": "entity name (must be related to the company)",
                            "sentiment": "positive/negative/neutral/mixed",
                            "key_point": "main sentiment about this company-related entity"
                        }
                    ]
                },
                "summary": "2-3 sentence summary focusing on the key company-related sentiment and reputation information"
            }
            
            Guidelines:
            1. Content Relevance Requirements:
               - Content MUST be directly about the target company or its immediate impact
               - Content MUST contain specific mentions of the company's actions, decisions, or effects
               - Content MUST provide clear sentiment or reputation indicators
               - Content MUST be recent and relevant to current company status
            
            2. Acceptable Content Types:
               - Direct company announcements and press releases
               - Customer reviews and feedback about the company
               - News about company performance and results
               - Analysis of company's market position and competition
               - Reports on company's products and services
               - Coverage of company's corporate actions and decisions
               - Discussion of company's leadership and management
               - Information about company's corporate responsibility and ESG
               - Coverage of company's innovation and development
               - Reports on company's workplace and culture
            
            3. Content to Exclude:
               - General industry news without specific company impact
               - Advertisements or promotional content
               - Job postings or recruitment information
               - Content about similarly named companies
               - General market commentary without company relevance
               - Historical information not relevant to current reputation
               - Technical specifications without reputation impact
               - Generic business advice or industry trends
            
            4. Cleaning and Structuring Requirements:
               - Remove all non-reputation-relevant content
               - Focus on sentiment-carrying phrases and words
               - Structure content into clear, reputation-focused sections
               - Preserve all company-specific information
               - Maintain context for sentiment analysis
            
            5. Sentiment Analysis Focus:
               - Analyze only company-specific sentiment
               - Consider both direct and indirect reputation impacts
               - Focus on current and recent events
               - Evaluate impact on key stakeholder groups
               - Assess both short-term and long-term reputation effects"""

            # Create the user message
            user_message = f"""Clean, structure, and analyze the sentiment of this content:

{content}

Focus on identifying sentiment toward key entities and providing a clean, well-structured version of the content."""

            # Make the API call
            response = await self.async_client.chat.completions.create(
                model=self.config.get('llm_model', "gpt-4.1-nano"),
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse and validate the response
            result = json.loads(response.choices[0].message.content)
            
            # Extract the needed information
            cleaned_content = result.get('cleaned_content', content)
            
            # Create metadata from the response
            metadata = {
                'entities': result.get('entities', []),
                'sentiment_analysis': result.get('sentiment_analysis', {}),
                'summary': result.get('summary', ''),
                'overall_sentiment': result.get('sentiment_analysis', {}).get('overall_sentiment', 'neutral'),
                'confidence_score': result.get('sentiment_analysis', {}).get('confidence', 0.5),
                'cleaning_timestamp': datetime.now().isoformat()
            }
            
            return {
                'cleaned_content': cleaned_content,
                'metadata': metadata
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding LLM response as JSON: {str(e)}")
            return {
                'cleaned_content': content,
                'metadata': {
                    'error': f"JSON decode error: {str(e)}",
                    'cleaning_timestamp': datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error in LLM processing: {str(e)}")
            return {
                'cleaned_content': content,
                'metadata': {
                    'error': str(e),
                    'cleaning_timestamp': datetime.now().isoformat()
                }
            }
    
    def _simple_validation(self, content, metadata):
        """Simplified validation to check basic content quality."""
        try:
            issues = []
            
            # Basic checks
            if len(content) < 100:
                issues.append("content_too_short")
            
            if re.search(r'<[^>]+>', content):
                issues.append("html_remnants")
            
            if 'entities' not in metadata or not metadata['entities']:
                issues.append("no_entities_extracted")
            
            return {
                'is_valid': len(issues) == 0,
                'issues': issues
            }
        except Exception as e:
            logger.error(f"Error in validation: {str(e)}")
            return {'is_valid': True, 'issues': []}
    
    def _get_all_cleaning_results(self):
        """Retrieve all cleaning results from the database."""
        try:
            cleaned_contents = self.db.query(CleanedContent).all()
            return {
                'results_count': len(cleaned_contents),
                'metrics': self.metrics,
                'contents': [
                    {
                        'id': cc.id,
                        'scraped_content_id': cc.scraped_content_id,
                        'basic_cleaned_content': cc.basic_cleaned_content[:100] + '...' if cc.basic_cleaned_content and len(cc.basic_cleaned_content) > 100 else cc.basic_cleaned_content,
                        'llm_cleaned_content': cc.llm_cleaned_content[:100] + '...' if cc.llm_cleaned_content and len(cc.llm_cleaned_content) > 100 else cc.llm_cleaned_content,
                        'metadata': json.loads(cc.cleaning_metadata) if cc.cleaning_metadata else {},
                        'created_at': cc.created_at.isoformat() if hasattr(cc, 'created_at') and cc.created_at else None
                    }
                    for cc in cleaned_contents
                ]
            }
        except Exception as e:
            logger.error(f"Error retrieving cleaning results: {str(e)}")
            return {'results_count': 0, 'metrics': self.metrics, 'contents': []}

def main():
    """Run the content cleaner"""
    # Create a cleaner with cost-effective configuration
    config = {
        'async_processing': True,
        'batch_size': 10,           # Larger batch for efficiency
        'llm_model': "gpt-4.1-nano", # More cost-effective model
        'basic_cleaning': True,
        'detect_content_type': True,
        'coreference_resolution': False,  # Disabled to save costs
        'segment_content': True,
        'llm_cleaning': True,
        'validation': True
    }
    
    cleaner = ContentCleaner(config)
    results = cleaner.clean_all_content()
    
    logger.info(f"Content cleaning completed. Processed {results['results_count']} articles.")
    logger.info(f"Successful: {results['metrics']['successful']}")
    logger.info(f"Failed: {results['metrics']['failed']}")
    logger.info(f"Processing time: {results['metrics']['processing_time']:.2f} seconds")
    logger.info(f"Average content length reduction: {results['metrics']['avg_content_length_reduction']:.2f}%")
    
    if results['metrics']['validation_issues']:
        logger.info("Validation issues encountered:")
        for issue, count in results['metrics']['validation_issues'].items():
            logger.info(f"- {issue}: {count}")

if __name__ == "__main__":
    main()