import json
import os
import requests
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SearchResult:
    """Class to store search results for a company."""
    def __init__(self, company_id, company_name, search_query, date_range):
        self.company_id = company_id
        self.company_name = company_name
        self.search_query = search_query
        self.date_range = date_range
        self.items = []
    
    def add_result(self, title, link, snippet):
        """Add a search result item."""
        self.items.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "search_date_range": self.date_range  # Include the date range with each result
        })
    
    def to_dict(self):
        """Convert the search result to a dictionary."""
        return {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "search_query": self.search_query,
            "date_range": self.date_range,
            "results": self.items,
            "result_count": len(self.items),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

class GoogleSearchAgent:
    """Agent to perform Google searches using the Custom Search API."""
    def __init__(self, api_key=None, search_engine_id=None, max_retries=3, retry_delay=2.0):
        # Get API credentials from environment variables if not provided
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.search_engine_id = search_engine_id or os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
        
        if not self.api_key:
            raise ValueError("Google API key not found. Set GOOGLE_API_KEY in your .env file.")
        if not self.search_engine_id:
            raise ValueError("Google Search Engine ID not found. Set GOOGLE_SEARCH_ENGINE_ID in your .env file.")
        
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def calculate_date_range(self, date_restrict):
        """Calculate the date range based on Google's dateRestrict parameter.
        
        Args:
            date_restrict: A string in the format of [d|m|y]<number> (e.g., 'd7', 'm1', 'y1')
                           where d=day, m=month, y=year
        
        Returns:
            A string representing the date range in the format "YYYY-MM-DD to YYYY-MM-DD"
        """
        today = datetime.now()
        
        if not date_restrict:
            return "All dates"
        
        try:
            period = date_restrict[0]
            number = int(date_restrict[1:])
            
            if period == 'd':
                start_date = today - timedelta(days=number)
                return f"Last {number} days ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
            elif period == 'm':
                start_date = today - timedelta(days=number * 30)  # Approximate
                return f"Last {number} month(s) ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
            elif period == 'y':
                start_date = today - timedelta(days=number * 365)  # Approximate
                return f"Last {number} year(s) ({start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')})"
            else:
                return f"Custom time range specified by {date_restrict}"
        except (IndexError, ValueError):
            return f"Invalid date restriction format: {date_restrict}"
    
    def search(self, query, country=None, date_restrict=None, num_results=10):
        """Perform a Google search using the Custom Search API.
        
        Args:
            query: The search query string
            country: The country code for geolocation filtering (gl parameter)
            date_restrict: Time restriction in Google format (e.g., 'd7', 'm1')
            num_results: Number of results to return (max 10 per request)
            
        Returns:
            The search results as a dictionary
        """
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': min(num_results, 10)  # Google API allows max 10 results per request
        }
        
        # Add optional parameters if provided
        if country:
            params['gl'] = country
        if date_restrict:
            params['dateRestrict'] = date_restrict
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Searching for: {query} (attempt {attempt+1}/{self.max_retries})")
                response = requests.get(self.base_url, params=params, timeout=30)
                
                if response.status_code == 429:  # Rate limit exceeded
                    wait_time = (2 ** attempt) * self.retry_delay
                    logger.warning(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry.")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error performing search: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * self.retry_delay
                    logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("All retry attempts failed")
                    return {"error": str(e)}
        
        return {"error": "Maximum retry attempts reached"}
    
    # Remove the extract_published_date method as we're no longer using it
    
    def process_search_query(self, search_obj, company_name_mapping=None):
        """Process a search query object and return the search results."""
        company_id = search_obj.get('company_id')
        search_query = search_obj.get('search_query')
        parameters = search_obj.get('parameters', {})
        
        # In our updated code, the company_id itself is a sanitized company name
        # We can use it directly if the mapping is not available
        if company_name_mapping and company_id in company_name_mapping:
            company_name = company_name_mapping[company_id]
        else:
            # If no mapping, try to unsanitize the ID (replace underscores with spaces)
            company_name = company_id.replace('_', ' ')
        
        # Get search parameters
        country = parameters.get('gl')
        date_restrict = parameters.get('dateRestrict')
        
        # Calculate date range
        date_range = self.calculate_date_range(date_restrict)
        
        # Create a search result object
        result = SearchResult(
            company_id=company_id,
            company_name=company_name,
            search_query=search_query,
            date_range=date_range
        )
        
        # Perform the search
        search_results = self.search(
            query=search_query,
            country=country,
            date_restrict=date_restrict,
            num_results=10  # Default to 10 results
        )
        
        # Check for errors
        if 'error' in search_results:
            logger.error(f"Search error for company {company_name}: {search_results['error']}")
            result.add_result(
                title="Error",
                link="",
                snippet=f"Search failed: {search_results.get('error')}"
            )
            return result
        
        # Process search results
        items = search_results.get('items', [])
        if not items:
            logger.warning(f"No search results found for company {company_name}")
            result.add_result(
                title="No results",
                link="",
                snippet="No search results found for this query."
            )
            return result
        
        # Add each search result - date range is already included in the SearchResult object
        for item in items:
            result.add_result(
                title=item.get('title', ''),
                link=item.get('link', ''),
                snippet=item.get('snippet', '')
            )
        
        logger.info(f"Found {len(items)} results for company {company_name}")
        return result

def load_search_queries(file_path):
    """Load search queries from the JSON file."""
    try:
        with open(file_path, 'r') as file:
            search_queries = json.load(file)
        
        if not isinstance(search_queries, list):
            logger.error("Invalid search queries file: expected a JSON array")
            return []
        
        logger.info(f"Loaded {len(search_queries)} search queries from {file_path}")
        return search_queries
    
    except Exception as e:
        logger.error(f"Error loading search queries: {e}")
        return []

def load_company_data(file_path):
    """Load company data to map company IDs to names."""
    try:
        with open(file_path, 'r') as file:
            companies = json.load(file)
        
        if not isinstance(companies, list):
            logger.error("Invalid company data file: expected a JSON array")
            return {}
        
        # Create a mapping of company_id to company_name
        company_mapping = {}
        for company in companies:
            if isinstance(company, dict):
                company_name = company.get('company_name')
                if company_name:
                    # With our updated generator, company_id is derived from name
                    sanitized_name = ''.join(c for c in company_name if c.isalnum() or c in [' ', '_'])
                    company_id = sanitized_name.strip().replace(' ', '_')
                    company_mapping[company_id] = company_name
        
        logger.info(f"Created mapping for {len(company_mapping)} companies")
        return company_mapping
    
    except Exception as e:
        logger.error(f"Error loading company data: {e}")
        return {}

def save_results(results, output_file):
    """Save search results to a JSON file."""
    try:
        with open(output_file, 'w') as file:
            json.dump(results, file, indent=2)
        logger.info(f"Search results saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving search results: {e}")
        return False

def batch_process_queries(search_queries, search_agent, company_mapping, batch_size=5, delay=2.0):
    """Process search queries in batches to avoid hitting rate limits."""
    results = []
    total = len(search_queries)
    
    for i in range(0, total, batch_size):
        batch = search_queries[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(total+batch_size-1)//batch_size}")
        
        for j, query in enumerate(batch):
            logger.info(f"  Processing query {i+j+1}/{total}: {query.get('search_query', '')}")
            result = search_agent.process_search_query(query, company_mapping)
            results.append(result.to_dict())
        
        # Add delay between batches (unless it's the last batch)
        if i + batch_size < total:
            logger.info(f"Batch complete. Waiting {delay} seconds before next batch...")
            time.sleep(delay)
    
    return results

def main():
    """Main function to run the search agent."""
    # Configuration
    SEARCH_QUERIES_FILE = "search_agent/search_results.json"
    COMPANY_DATA_FILE = "companies.json"
    OUTPUT_FILE = "search_agent/web_mentions.json"
    BATCH_SIZE = 5  # Process 5 queries at a time
    BATCH_DELAY = 2.0  # 2 second delay between batches
    
    print("\n" + "="*60)
    print(" Company Web Mentions Search Agent ".center(60, "="))
    print("="*60 + "\n")
    
    try:
        # Load search queries
        print(f"Loading search queries from {SEARCH_QUERIES_FILE}...")
        search_queries = load_search_queries(SEARCH_QUERIES_FILE)
        if not search_queries:
            print("No search queries found. Please run the search query generator first.")
            return
        
        # Load company data to get company names
        print(f"Loading company data from {COMPANY_DATA_FILE}...")
        company_mapping = load_company_data(COMPANY_DATA_FILE)
        
        # Initialize the search agent
        print("Initializing Google Search agent...")
        search_agent = GoogleSearchAgent()
        
        # Process search queries in batches
        print(f"Processing {len(search_queries)} search queries in batches of {BATCH_SIZE}...")
        results = batch_process_queries(
            search_queries=search_queries,
            search_agent=search_agent,
            company_mapping=company_mapping,
            batch_size=BATCH_SIZE,
            delay=BATCH_DELAY
        )
        
        # Save results
        results_dict = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_companies": len(results),
            "results": results
        }
        
        save_results(results_dict, OUTPUT_FILE)
        
        # Print sample results
        if results:
            print("\nSample of search results:")
            sample_size = min(2, len(results))
            for i in range(sample_size):
                result = results[i]
                print(f"{i+1}. Company: {result['company_name']}")
                print(f"   Search query: {result['search_query']}")
                print(f"   Date range: {result['date_range']}")
                print(f"   Results found: {result['result_count']}")
                if result['results'] and result['result_count'] > 0 and len(result['results']) > 0:
                    sample_result = result['results'][0]
                    print(f"   Sample result: {sample_result['title']}")
                    print(f"   Link: {sample_result['link']}")
                print()
            
            print(f"Successfully processed {len(results)} companies")
            print(f"All results saved to: {OUTPUT_FILE}")
        else:
            print("No search results were generated. Check logs for errors.")
        
    except Exception as e:
        print(f"Error during execution: {e}")
        logger.error(f"Error during execution: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        main()
        print("\nScript completed successfully.")
    except Exception as e:
        print(f"\nError: {e}")
        print("Script execution failed. Check the logs for details.")
    
    print("\nNote: Make sure you have:")
    print("  1. A valid 'search_results.json' file from running the query generator")
    print("  2. A .env file with GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID")
    print("  3. Sufficient API credits for Google Custom Search API (100 queries free per day)")