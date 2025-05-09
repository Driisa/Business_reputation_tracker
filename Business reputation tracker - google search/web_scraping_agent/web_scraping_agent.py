import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraping.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("content_scraper")

def get_processed_files():
    """Get list of already processed files"""
    script_dir = Path(__file__).parent.parent
    processed_file = script_dir / 'web_scraping_agent' / 'processed_files.json'
    
    if processed_file.exists():
        try:
            with open(processed_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except json.JSONDecodeError:
            return set()
    return set()

def save_processed_file(filename):
    """Save a processed file to the tracking list"""
    script_dir = Path(__file__).parent.parent
    processed_file = script_dir / 'web_scraping_agent' / 'processed_files.json'
    
    processed_files = get_processed_files()
    processed_files.add(filename)
    
    with open(processed_file, 'w', encoding='utf-8') as f:
        json.dump(list(processed_files), f)

class ContentScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.last_request_time = 0
        self.request_delay = 1  # 1 second between requests

    def _respect_rate_limits(self):
        """Ensure we don't request too quickly"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
        self.last_request_time = time.time()

    def scrape_url(self, url):
        try:
            self._respect_rate_limits()
            
            logger.info(f"Scraping: {url}")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            self.raw_html = response.text  # Store for ratio calculation
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content
            content = self._extract_content(soup)
            
            # Validate content
            is_valid = self._validate_content(content, url)
            if not is_valid:
                return {
                    'content': '', 
                    'date': None, 
                    'valid': False, 
                    'error': 'Content validation failed'
                }
            
            # Extract date
            date = self._extract_date(soup)
            valid_date = self._validate_date(date, url)
            
            return {
                'content': content,
                'date': date if valid_date else None,
                'valid': True
            }
                
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Error scraping {url}: {error_type} - {str(e)}")
            return {
                'content': '',
                'date': None,
                'valid': False,
                'error': f"{error_type}: {str(e)}"
            }

    def _extract_content(self, soup):
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text content
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text

    def _validate_content(self, content, url):
        """Validate that scraped content is meaningful"""
        # Check if content is too short (possibly failed scrape)
        if len(content) < 100:
            logger.warning(f"Content from {url} is suspiciously short ({len(content)} chars)")
            return False
            
        # Check for error indicators in content
        error_patterns = ['access denied', 'captcha', 'not found', '404', 'blocked',
                         'robot', 'unauthorized', 'forbidden', 'unavailable']
        content_lower = content.lower()
        for pattern in error_patterns:
            if pattern in content_lower:
                logger.warning(f"Content from {url} may contain access errors (detected: {pattern})")
                return False
                
        # Check content-to-html ratio (low ratio often indicates scraping failure)
        if hasattr(self, 'raw_html') and self.raw_html:
            content_ratio = len(content) / len(self.raw_html)
            if content_ratio < 0.01:
                logger.warning(f"Content-to-HTML ratio for {url} is suspiciously low ({content_ratio:.4f})")
                return False
                
        return True

    def _extract_date(self, soup):
        # Common date patterns in meta tags
        date_patterns = [
            'article:published_time',
            'og:published_time',
            'datePublished',
            'date',
            'publishedDate'
        ]
        
        # Check meta tags
        for pattern in date_patterns:
            meta = soup.find('meta', property=pattern) or soup.find('meta', attrs={'name': pattern})
            if meta and meta.get('content'):
                return meta['content']
        
        # Look for date in article tags
        time_tag = soup.find('time')
        if time_tag and time_tag.get('datetime'):
            return time_tag['datetime']
            
        # Look for date in text content
        date_pattern = r'\d{4}-\d{2}-\d{2}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}'
        text = soup.get_text()
        match = re.search(date_pattern, text)
        if match:
            return match.group()
            
        return None
        
    def _validate_date(self, date, url):
        """Validate that the extracted date is reasonable"""
        if not date:
            return False
            
        try:
            # Try to standardize the date format
            if re.match(r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}', date):
                parsed_date = datetime.strptime(date, '%d %b %Y')
            else:
                # Try ISO format or similar
                parsed_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
                
            # Validate the date is reasonable (not in the future, not too old)
            current_date = datetime.now()
            if parsed_date.year < 2000 or parsed_date > current_date:
                logger.warning(f"Date from {url} seems invalid: {date}")
                return False
                
            return True
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse date format from {url}: {date} - {str(e)}")
            return False

def process_search_results(company_name):
    """Process search results for a company and scrape content."""
    script_dir = Path(__file__).parent.parent
    search_results_dir = script_dir / 'perplexica_search_agent' / 'search_results'
    output_dir = script_dir / 'web_scraping_agent' / 'scraped_results'
    output_dir.mkdir(exist_ok=True)
    
    # Get current date for filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    input_file = search_results_dir / f"search_results_{company_name.lower()}_{current_date}.json"
    if not input_file.exists():
        logger.error(f"Search results not found for {company_name} on {current_date}")
        return
        
    # Check if this file has already been processed
    if str(input_file) in get_processed_files():
        logger.info(f"File {input_file} has already been processed. Skipping.")
        return
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            search_results = json.load(f)
        
        scraper = ContentScraper()
        processed_results = []
        
        # Track validation statistics
        valid_count = 0
        invalid_count = 0
        errors = {}
        
        total_urls = sum(1 for result in search_results['results'] if result['metadata'].get('url'))
        
        for result in search_results['results']:
            url = result['metadata'].get('url')
            if not url:
                continue
                
            scraped_data = scraper.scrape_url(url)
            
            processed_result = {
                'title': result['metadata'].get('title', ''),
                'url': url,
                'content': scraped_data['content'],
                'published_date': scraped_data['date'],
                'type': result['metadata'].get('type', 'unknown'),
                'valid': scraped_data['valid']
            }
            
            if scraped_data['valid']:
                valid_count += 1
            else:
                invalid_count += 1
                errors[url] = scraped_data.get('error', 'Unknown error')
                
            processed_results.append(processed_result)
            
        # Save processed results with date in filename
        output_file = output_dir / f"scraped_results_{company_name.lower()}_{current_date}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_results, f, indent=2, ensure_ascii=False)
            
        # Mark this file as processed
        save_processed_file(str(input_file))
            
        logger.info(f"Processed {total_urls} URLs for {company_name}")
        logger.info(f"Valid results: {valid_count}")
        logger.info(f"Invalid results: {invalid_count}")
        if errors:
            logger.warning(f"Errors encountered: {json.dumps(errors, indent=2)}")
            
    except Exception as e:
        logger.error(f"Error processing search results for {company_name}: {str(e)}")

def main():
    script_dir = Path(__file__).parent.parent
    companies_file = script_dir / 'perplexica_search_agent' / 'companies.json'
    
    try:
        with open(companies_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if 'companies' not in data:
            logger.error("'companies' key not found in JSON file")
            return
            
        for company in data['companies']:
            company_name = company['name']
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing company: {company_name}")
            logger.info(f"{'='*50}")
            
            process_search_results(company_name)
            
    except Exception as e:
        logger.error(f"Error processing companies: {e}")

if __name__ == "__main__":
    main()