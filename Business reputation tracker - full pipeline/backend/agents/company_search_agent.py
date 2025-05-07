import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from backend.app.database import SearchResult, Company, get_db_session

class CompanySearchAgent:
    def __init__(self):
        """Initialize the search agent with API credentials from .env file."""
        load_dotenv()
        self.api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.cx = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.db = get_db_session()
    
    def search_companies(self):
        """Search for mentions of companies from the database from last 24 hours."""
        try:
            # Get all companies from the database
            companies = self.db.query(Company).all()
            
            if not companies:
                print("No companies found in the database")
                return {}
            
            # Process each company
            for company in companies:
                print(f"Searching for mentions of {company.name}...")
                results = self.search_single_company(company.name)
                self._save_to_database(company.name, results)
                time.sleep(2)  # Avoid hitting API rate limits
            
            return self._get_all_results()
            
        except Exception as e:
            print(f"Error searching companies: {str(e)}")
            return {}
    
    def _save_to_database(self, company_name, results):
        """Save search results to the database."""
        try:
            # Get the company
            company = self.db.query(Company).filter_by(name=company_name).first()
            if not company:
                print(f"Company {company_name} not found in database")
                return

            for mention in results.get('mentions', []):
                # Check if this URL already exists in the database
                existing_result = self.db.query(SearchResult).filter_by(url=mention['link']).first()
                if existing_result:
                    print(f"Article already exists in database: {mention['link']}")
                    continue

                search_result = SearchResult(
                    company_id=company.id,
                    query=company_name,
                    url=mention['link'],
                    title=mention['title'],
                    snippet=mention['snippet']
                )
                self.db.add(search_result)
            
            self.db.commit()
        except Exception as e:
            print(f"Error saving to database: {str(e)}")
            self.db.rollback()
    
    def _get_all_results(self):
        """Retrieve all search results from the database."""
        try:
            results = self.db.query(SearchResult).all()
            return {
                'results_count': len(results),
                'mentions': [
                    {
                        'title': r.title,
                        'link': r.url,
                        'snippet': r.snippet,
                        'query': r.query,
                        'created_at': r.created_at.isoformat()
                    }
                    for r in results
                ]
            }
        except Exception as e:
            print(f"Error retrieving results from database: {str(e)}")
            return {'results_count': 0, 'mentions': []}

    def search_single_company(self, company_name):
        """Search for mentions of a single company in the last 24 hours."""
        try:
            # Simple search query for recent mentions
            search_query = f'"{company_name}"'
            
            print(f"Searching for: {search_query}")
            results = []
            
            if self.api_key and self.cx:
                params = {
                    'q': search_query,
                    'key': self.api_key,
                    'cx': self.cx,
                    'num': 10,  # Get 10 results
                    'sort': 'date',
                    'dateRestrict': 'd1'  # Last 24 hours
                }
                
                try:
                    response = self.session.get("https://www.googleapis.com/customsearch/v1", params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'items' in data:
                        for item in data['items']:
                            results.append({
                                'title': item.get('title', ''),
                                'link': item.get('link', ''),
                                'snippet': item.get('snippet', '')
                            })
                        print(f"Found {len(results)} results")
                    else:
                        print("No results found")
                        
                except Exception as e:
                    print(f"API search error: {str(e)}")
            
            return {
                'company': company_name,
                'search_date': datetime.now().isoformat(),
                'results_count': len(results),
                'mentions': results
            }
            
        except Exception as e:
            print(f"Error searching for {company_name}: {str(e)}")
            return {
                'company': company_name,
                'search_date': datetime.now().isoformat(),
                'results_count': 0,
                'mentions': []
            }

def main():
    """Run the company search"""
    agent = CompanySearchAgent()
    agent.search_companies()
    print("Search completed.")

if __name__ == "__main__":
    main()