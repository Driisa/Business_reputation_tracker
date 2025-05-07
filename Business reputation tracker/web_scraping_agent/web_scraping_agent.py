import time
import re
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime
import os

class ContentScraper:
    def __init__(self):
        """Initialize the content scraper."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape_all_urls(self):
        """Scrape content from all URLs in the search results JSON file."""
        # Read the search results JSON file
        json_path = os.path.join('company_search_agent', 'search_results.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            search_data = json.load(f)
        
        # Extract all URLs from the search results
        urls_to_scrape = []
        for company_result in search_data['results']:
            for result in company_result['results']:
                urls_to_scrape.append({
                    'url': result['link'],
                    'title': result['title'],
                    'company': company_result['company']
                })
        
        print(f"Found {len(urls_to_scrape)} URLs to scrape")
        
        # Process each URL
        scraped_results = []
        for url_data in urls_to_scrape:
            try:
                print(f"Scraping content from {url_data['url']}")
                content_data = self.scrape_url(url_data['url'])
                
                # Skip if content extraction failed
                if not content_data.get('content'):
                    print(f"No content extracted from {url_data['url']}, skipping...")
                    continue
                
                # Add additional metadata
                content_data['original_title'] = url_data['title']
                content_data['company'] = url_data['company']
                content_data['scraped_date'] = datetime.now().isoformat()
                content_data['url'] = url_data['url']
                
                scraped_results.append(content_data)
                
                # Respect websites by waiting between requests
                time.sleep(2)
            except Exception as e:
                print(f"Error scraping {url_data['url']}: {str(e)}")
                continue
        
        # Save all results to a single JSON file
        output_data = {
            'scraped_date': datetime.now().isoformat(),
            'total_pages_scraped': len(scraped_results),
            'results': scraped_results
        }
        
        output_file = os.path.join('web_scraping_agent', f'scraped_content.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"Saved scraped content to {output_file}")
        
        return output_data
    
    def scrape_url(self, url):
        """Scrape content from a single URL."""
        result = {'title': '', 'content': '', 'date': ''}
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title_tag = soup.find('title')
            result['title'] = title_tag.text.strip() if title_tag else ''
            
            # Extract date - look for common date meta tags
            date = self._extract_date(soup)
            result['date'] = date if date else ''
            
            # Extract main content - this is more complex and depends on site structure
            content = self._extract_content(soup)
            result['content'] = content if content else ''
            
            return result
        except Exception as e:
            print(f"Error in scrape_url for {url}: {str(e)}")
            # Return empty result to indicate failure
            return result
    
    def _extract_date(self, soup):
        """Extract publication date from HTML."""
        # Try common meta tags for date
        date_meta_tags = [
            'meta[property="article:published_time"]',
            'meta[property="og:published_time"]',
            'meta[name="pubdate"]',
            'meta[name="publishdate"]',
            'meta[name="date"]',
            'time[datetime]',
            'time[class*="publish"]',
            'span[class*="date"]'
        ]
        
        for selector in date_meta_tags:
            date_element = soup.select_one(selector)
            if date_element:
                if date_element.name == 'meta':
                    return date_element.get('content', '')
                elif date_element.name == 'time':
                    return date_element.get('datetime', '') or date_element.text.strip()
                else:
                    return date_element.text.strip()
        
        # Look for structured data
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'datePublished' in data:
                        return data['datePublished']
                    elif 'dateCreated' in data:
                        return data['dateCreated']
            except:
                pass
        
        return ''
    
    def _extract_content(self, soup):
        """Extract main content from the webpage."""
        # Remove unwanted elements
        for element in soup.select('script, style, nav, header, footer, iframe, aside, [class*="comment"], [class*="banner"], [class*="ad-"], [class*="related"], [id*="related"]'):
            element.decompose()
        
        # Try to find the main content container using common patterns
        content_selectors = [
            'article', 
            '[class*="article-body"]', 
            '[class*="post-content"]',
            '[class*="entry-content"]', 
            '[class*="story-content"]',
            '[class*="content-article"]',
            '[class*="main-content"]',
            '[class*="story-body"]',
            'main',
            '.content',
            '#content'
        ]
        
        # Try each selector
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                # Get all the paragraphs within this element
                paragraphs = content_element.find_all('p')
                if paragraphs:
                    content = '\n\n'.join(p.get_text().strip() for p in paragraphs)
                    if len(content) > 100:  # Reasonable content should be longer than 100 chars
                        return content
                
                # If no paragraphs or too short, just return the full text
                content = content_element.get_text().strip()
                # Clean up whitespace
                content = re.sub(r'\s+', ' ', content)
                if len(content) > 100:
                    return content
        
        # If all else fails, just get all paragraphs
        paragraphs = soup.find_all('p')
        if paragraphs:
            content = '\n\n'.join(p.get_text().strip() for p in paragraphs)
            if len(content) > 100:
                return content
        
        # Last resort: get the body text
        body = soup.find('body')
        if body:
            # Remove all link-only text nodes
            links = body.find_all('a')
            for link in links:
                if len(link.get_text(strip=True)) < 100:
                    link.decompose()
            
            content = body.get_text(separator=' ', strip=True)
            content = re.sub(r'\s+', ' ', content)
            return content
        
        return ''

def main():
    """Run the content scraper"""
    scraper = ContentScraper()
    results = scraper.scrape_all_urls()
    print(f"Content scraping completed. Scraped {results['total_pages_scraped']} pages.")

if __name__ == "__main__":
    main()