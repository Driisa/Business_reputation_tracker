import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import requests
from bs4 import BeautifulSoup
import time
import logging
from urllib.parse import urlparse
import os
from typing import List, Dict, Any, Union
import re
from datetime import datetime
from data.pipeline_db_config import SessionLocal
from data.pipeline_db_models import SearchResult, ScrapedContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("content_scraper")

class ContentScraper:
    def __init__(self, user_agent=None, delay=2):
        """Initialize the content scraper with custom settings.
        
        Args:
            user_agent: Custom user agent string (defaults to Chrome)
            delay: Delay between requests in seconds
        """
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        self.delay = delay
        
    def get_relevant_urls_from_db(self, session) -> Dict[str, List[Dict[str, Any]]]:
        """Extract URLs from highly relevant and relevant categories from database.
        
        Returns:
            Dictionary mapping company names to lists of relevant URLs and metadata
        """
        company_urls = {}
        
        # Query search results that are highly relevant or relevant
        search_results = session.query(SearchResult).filter(
            SearchResult.relevance_category.in_(['highly_relevant', 'relevant'])
        ).all()
        
        for result in search_results:
            company_name = result.company_name
            if not company_name:
                continue
                
            if company_name not in company_urls:
                company_urls[company_name] = []
                
            company_urls[company_name].append({
                "url": result.link,
                "search_result_id": result.id
            })
                
        return company_urls
    
    def clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and normalizing."""
        if not text:
            return ""
            
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        # Remove leading/trailing whitespace
        text = text.strip()
        # Normalize unicode characters
        text = text.replace('\xa0', ' ')
        return text
    
    def extract_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract structured content from a BeautifulSoup object."""
        content = {
            "title": "",
            "meta_description": "",
            "main_content": "",
            "publication_date": "",
            "author": "",
            "tags": []
        }
        
        # Extract title
        if soup.title:
            content["title"] = self.clean_text(soup.title.string)
        
        # Extract meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and "content" in meta_desc.attrs:
            content["meta_description"] = self.clean_text(meta_desc["content"])
        
        # Try to find publication date
        date_candidates = []
        time_elements = soup.find_all("time")
        for time in time_elements:
            if "datetime" in time.attrs:
                date_candidates.append(time["datetime"])
            elif time.string:
                date_candidates.append(time.string)
        
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date and "content" in meta_date.attrs:
            date_candidates.append(meta_date["content"])
        
        date_patterns = [
            r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, str(soup), re.IGNORECASE)
            date_candidates.extend(matches)
        
        if date_candidates:
            content["publication_date"] = date_candidates[0]
        
        # Extract author information
        author_candidates = []
        author_elements = soup.find_all(["a", "span", "div"], class_=re.compile(r'author|byline', re.IGNORECASE))
        for element in author_elements:
            author_text = self.clean_text(element.get_text())
            if author_text and len(author_text) < 100:
                author_candidates.append(author_text)
        
        author_meta = soup.find("meta", attrs={"property": "article:author"})
        if author_meta and "content" in author_meta.attrs:
            author_candidates.append(author_meta["content"])
        
        if author_candidates:
            content["author"] = author_candidates[0]
        
        # Extract main content
        main_content_containers = soup.find_all(["article", "main", "div"], 
                                              class_=re.compile(r'article|post|content|entry', re.IGNORECASE))
        
        all_paragraphs = soup.find_all("p")
        
        paragraphs_text = []
        for p in all_paragraphs:
            p_text = self.clean_text(p.get_text())
            if p_text and len(p_text) > 20:
                paragraphs_text.append(p_text)
        
        if paragraphs_text:
            content["main_content"] = "\n\n".join(paragraphs_text)
        else:
            for container in main_content_containers:
                container_text = self.clean_text(container.get_text())
                if container_text and len(container_text) > 200:
                    content["main_content"] = container_text
                    break
        
        # Extract tags/categories
        tag_elements = soup.find_all(["a", "span", "li"], 
                                  class_=re.compile(r'tag|category|topic', re.IGNORECASE))
        for tag in tag_elements:
            tag_text = self.clean_text(tag.get_text())
            if tag_text and len(tag_text) < 30:
                content["tags"].append(tag_text)
        
        return content
    
    def scrape_url(self, url: str) -> Dict[str, Any]:
        """Scrape content from a given URL."""
        if not url:
            return {"error": "Empty URL provided"}
            
        try:
            result = {
                "url": url,
                "domain": urlparse(url).netloc,
                "scrape_time": datetime.now()
            }
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result["content_type"] = response.headers.get("Content-Type", "")
            result["encoding"] = response.encoding
            
            if "text/html" not in result["content_type"]:
                result["error"] = f"Not HTML content: {result['content_type']}"
                return result
            
            soup = BeautifulSoup(response.text, 'html.parser')
            extracted_content = self.extract_content(soup)
            result.update(extracted_content)
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "url": url,
                "error": str(e),
                "domain": urlparse(url).netloc,
                "scrape_time": datetime.now()
            }
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return {
                "url": url,
                "error": f"Unexpected error: {str(e)}",
                "domain": urlparse(url).netloc,
                "scrape_time": datetime.now()
            }
    
    def scrape_company_data(self, session) -> None:
        """Scrape content from relevant URLs for all companies and save to database."""
        # Extract relevant URLs for each company
        company_urls = self.get_relevant_urls_from_db(session)
        
        # Scrape each URL for each company
        for company_name, urls_list in company_urls.items():
            logger.info(f"Scraping {len(urls_list)} URLs for {company_name}")
            
            new_content_count = 0
            duplicate_content_count = 0
            
            for url_data in urls_list:
                url = url_data.get("url", "")
                search_result_id = url_data.get("search_result_id")
                if not url or not search_result_id:
                    continue
                
                # Check if content for this search result already exists
                existing_content = session.query(ScrapedContent).filter(
                    ScrapedContent.search_result_id == search_result_id
                ).first()
                
                if existing_content:
                    duplicate_content_count += 1
                    logger.debug(f"Skipping duplicate content for URL: {url}")
                    continue
                
                logger.info(f"  Scraping: {url}")
                
                # Scrape the URL
                scraped_data = self.scrape_url(url)
                
                # Create ScrapedContent record
                scraped_content = ScrapedContent(
                    search_result_id=search_result_id,
                    domain=scraped_data.get("domain", ""),
                    main_content=scraped_data.get("main_content", ""),
                    status="new"
                )
                
                # Add to session
                session.add(scraped_content)
                new_content_count += 1
                
                # Delay between requests
                time.sleep(self.delay)
            
            # Commit after each company to avoid large transactions
            try:
                session.commit()
                logger.info(f"  Saved {new_content_count} new scraped content items for {company_name} to database")
                if duplicate_content_count > 0:
                    logger.info(f"  Skipped {duplicate_content_count} duplicate content items for {company_name}")
            except Exception as e:
                logger.error(f"Error saving to database for {company_name}: {e}")
                session.rollback()


def scrape_relevant_content():
    """Main function for scraping relevant content from database."""
    session = SessionLocal()
    try:
        # Initialize the content scraper
        scraper = ContentScraper(delay=3)  # 3-second delay between requests
        
        # Scrape all relevant content and save to database
        scraper.scrape_company_data(session)
        
        logger.info("Completed scraping content for all companies")
    except Exception as e:
        logger.error(f"Error during scraping process: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape content from relevant URLs in database')
    parser.add_argument('--delay', type=int, default=3, 
                        help='Delay between requests in seconds')
    
    args = parser.parse_args()
    
    # Run the scraping process
    scrape_relevant_content()