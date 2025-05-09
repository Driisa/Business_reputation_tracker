import json
import requests
import os
import uuid
import time
from typing import List, Dict, Any, Optional
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Company:
    def __init__(self, data: Dict[str, Any]):
        self.company_name = data.get("company_name", "")
        self.description = data.get("description", "")
        self.industry = data.get("industry", "")
        self.country = data.get("country", "")
        # Ensure country is in proper format (2-letter ISO code)
        if self.country and len(self.country) != 2:
            logger.warning(f"Country code for {self.company_name} should be a 2-letter ISO code. Got: {self.country}")
        self.services = data.get("services", [])
        # Use company name as ID (sanitized) or provided ID if available
        if "company_id" in data:
            self.company_id = data["company_id"]
        else:
            # Convert company name to a valid ID by removing special chars
            sanitized_name = ''.join(c for c in self.company_name if c.isalnum() or c in [' ', '_'])
            self.company_id = sanitized_name.strip().replace(' ', '_')
    
    def validate(self) -> bool:
        """Validate that the company has all required fields."""
        if not self.company_name:
            logger.error(f"Company missing required field: company_name")
            return False
        return True

class SearchObject:
    def __init__(self, company_id: str, search_query: str, country: str, timespan: str = "last_7_days", country_restrict: str = None):
        self.company_id = company_id
        self.search_query = search_query
        
        # Convert time format to Google API format
        google_time_format = self._convert_timespan_to_google_format(timespan)
        
        # Determine language based on country code
        language = self._get_language_from_country(country)
        
        # Set top level domain for site search based on country
        tld = country.lower() if country else ""
        
        # Use Google API compatible parameters
        self.parameters = {
            # "gl": country.lower() if country else "",  # Google uses 'gl' for geolocation
            "dateRestrict": google_time_format,  # Google uses 'dateRestrict' for time filtering
            # "cr": country_restrict if country_restrict else "",  # Restricts search results to documents from a specific country
            "lr": f"lang_{language}" if language else "",  # Language restrict - limits results to a specific language
            "hl": language if language else "",  # Host language - sets the interface language for search results
            "num": 10,  # Number of results to return (max is typically 10)
            # "as_sitesearch": f".{tld}" if tld and tld != "us" else ""  # Restrict to specific domain TLD (e.g., .dk for Denmark)
        }
    
    def _get_language_from_country(self, country: str) -> str:
        """Map country code to primary language code."""
        country_to_language = {
            "dk": "da",  # Denmark -> Danish
            "se": "sv",  # Sweden -> Swedish
            "no": "no",  # Norway -> Norwegian
            "fi": "fi",  # Finland -> Finnish
            "de": "de",  # Germany -> German
            "fr": "fr",  # France -> French
            "es": "es",  # Spain -> Spanish
            "it": "it",  # Italy -> Italian
            "nl": "nl",  # Netherlands -> Dutch
            "pt": "pt",  # Portugal -> Portuguese
            "pl": "pl",  # Poland -> Polish
            "cz": "cs",  # Czech Republic -> Czech
            "gr": "el",  # Greece -> Greek
            "ru": "ru",  # Russia -> Russian
            "jp": "ja",  # Japan -> Japanese
            "cn": "zh-CN",  # China -> Chinese (Simplified)
            "kr": "ko",  # South Korea -> Korean
            # Default for English-speaking countries
            "us": "en",
            "gb": "en",
            "ca": "en",
            "au": "en",
            "nz": "en",
            "ie": "en",
            # Add more mappings as needed
        }
        
        if not country:
            return ""
        
        return country_to_language.get(country.lower(), "")
    
    def _convert_timespan_to_google_format(self, timespan: str) -> str:
        """Convert the friendly timespan format to Google Search API format."""
        if timespan == "last_7_days":
            return "d7"
        elif timespan == "last_month":
            return "m1"
        elif timespan == "last_3_months":
            return "m3"
        elif timespan == "last_year":
            return "y1"
        else:
            # Try to parse custom format if it follows pattern like "last_X_days"
            try:
                parts = timespan.split('_')
                if len(parts) == 3 and parts[0] == "last" and parts[2] in ["days", "months", "years"]:
                    number = int(parts[1])
                    if parts[2] == "days":
                        return f"d{number}"
                    elif parts[2] == "months":
                        return f"m{number}"
                    elif parts[2] == "years":
                        return f"y{number}"
            except (ValueError, IndexError):
                pass
            
            # Default to last 7 days if format is unknown
            return "d7"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "company_id": self.company_id,
            "search_query": self.search_query,
            "parameters": self.parameters
        }

class SearchQueryGenerator:
    def __init__(self, 
                 api_key: str, 
                 model: str = "gpt-4.1-nano", 
                 api_base: Optional[str] = None,
                 max_retries: int = 3,
                 retry_delay: float = 2.0):
        self.api_key = api_key
        self.model = model
        self.system_prompt = """You are an expert search query specialist focused on corporate intelligence.
Your task is to craft evergreen search queries that will find relevant and recent information about companies 
without relying on specific product version numbers or time-sensitive details that will quickly become outdated."""
        self.max_tokens = 150
        self.temperature = 0.3
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Allow custom API base URL
        self.api_base = api_base if api_base else "https://api.openai.com"
        self.api_endpoint = f"{self.api_base}/v1/chat/completions"
    
    def generate_query_for_company(self, company: Company, timespan: str = "last_month", country_restrict: str = None) -> SearchObject:
        """Generate an optimized search query for a company using GPT-4.1-nano."""
        
        # Validate the company
        if not company.validate():
            # Return a basic search query if validation fails
            logger.warning(f"Generating basic query for invalid company: {company.company_id}")
            return SearchObject(
                company_id=company.company_id,
                search_query=f'"{company.company_name}"',
                country=company.country,
                timespan=timespan,
                country_restrict=country_restrict
            )
        
        # Create the user prompt with instructions for evergreen search terms
        user_prompt = f"""
        Generate an evergreen search query to find recent news about this company that won't quickly become outdated:
        
        Company Name: {company.company_name}
        Description: {company.description}
        Industry: {company.industry}
        Country: {company.country}
        Services: {', '.join(company.services)}
        
        Your search query should:
        1. ALWAYS include the EXACT company name in quotes (e.g., "Acme Corporation")
        2. Include broad product CATEGORIES or technology AREAS (NOT specific model numbers or versions)
           - GOOD: "smartphones" "cloud services" "electric vehicles"
           - BAD: "iPhone 15" "Windows 11" "Model Y"
        3. Include 2-3 core business areas or distinctive technologies that define the company
        4. Include the company's stock ticker if it's publicly traded
        5. Consider common alternative names (e.g., "Meta" OR "Facebook")

        For non-English companies, keep the query simple and focus on the essential terms.
        
        Format your response as a single search query string ONLY. Do not include any explanation.
        Example format: "Company Name" core-business-areas product-category stock-ticker
        """
        
        # Make the API call to GPT-4.1-nano with retry logic
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Making API request for company: {company.company_name} (attempt {attempt+1}/{self.max_retries})")
                response = requests.post(self.api_endpoint, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 429:  # Rate limit exceeded
                    wait_time = (2 ** attempt) * self.retry_delay  # Exponential backoff
                    logger.warning(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry.")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()  # Raise an exception for other HTTP errors
                
                # Extract the generated search query from the response
                result = response.json()
                search_query = result["choices"][0]["message"]["content"].strip()
                
                logger.info(f"Generated query for {company.company_name}: {search_query}")
                
                # Create and return a SearchObject
                return SearchObject(
                    company_id=company.company_id,
                    search_query=search_query,
                    country=company.country,
                    timespan=timespan,
                    country_restrict=country_restrict
                )
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error calling API for {company.company_name}: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * self.retry_delay
                    logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    # Return a basic search query as fallback after all retries fail
                    logger.warning(f"All retries failed for {company.company_name}. Using fallback query.")
                    return SearchObject(
                        company_id=company.company_id,
                        search_query=f'"{company.company_name}"',
                        country=company.country,
                        timespan=timespan,
                        country_restrict=country_restrict
                    )
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing API response for {company.company_name}: {e}")
                # Return a basic search query as fallback
                return SearchObject(
                    company_id=company.company_id,
                    search_query=f'"{company.company_name}"',
                    country=company.country,
                    timespan=timespan,
                    country_restrict=country_restrict
                )
        
        # If we get here, all retries failed
        return SearchObject(
            company_id=company.company_id,
            search_query=f'"{company.company_name}"',
            country=company.country,
            timespan=timespan,
            country_restrict=country_restrict
        )

def batch_process_companies(companies: List[Company], 
                           generator: SearchQueryGenerator, 
                           batch_size: int = 10, 
                           delay_between_batches: float = 5.0,
                           timespan: str = "last_month",
                           country_restrict: str = None) -> List[Dict[str, Any]]:
    """Process companies in batches with delays between batches to avoid rate limits."""
    
    search_objects = []
    total = len(companies)
    
    for i in range(0, total, batch_size):
        batch = companies[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(total+batch_size-1)//batch_size}: companies {i+1}-{min(i+batch_size, total)}")
        
        for j, company in enumerate(batch):
            logger.info(f"  Processing company {i+j+1}/{total}: {company.company_name}")
            # Generate country restriction from company's country attribute if available
            company_cr = f"country{company.country.upper()}" if company.country else country_restrict
            search_obj = generator.generate_query_for_company(company, timespan, company_cr)
            search_objects.append(search_obj.to_dict())
        
        # Add delay between batches unless this is the last batch
        if i + batch_size < total:
            logger.info(f"Batch complete. Waiting {delay_between_batches:.2f} seconds before next batch...")
            time.sleep(delay_between_batches)
    
    logger.info(f"Generated search queries for {len(search_objects)} companies")
    return search_objects

def load_companies(input_path: str) -> List[Company]:
    """Load and validate company data from a JSON file or string."""
    try:
        # Check if input_path is a file or a JSON string
        if os.path.isfile(input_path):
            with open(input_path, 'r') as file:
                companies_data = json.load(file)
        else:
            # Try parsing as a JSON string
            companies_data = json.loads(input_path)
        
        # Validate overall structure
        if not isinstance(companies_data, list):
            logger.error("Input data must be a JSON array of company objects")
            return []
        
        # Create and validate Company objects
        companies = []
        for i, data in enumerate(companies_data):
            if not isinstance(data, dict):
                logger.warning(f"Skipping item {i}: not a valid company object")
                continue
            
            company = Company(data)
            if company.validate():
                companies.append(company)
        
        logger.info(f"Loaded {len(companies)} valid companies from input")
        return companies
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading companies: {e}")
        return []

def save_output(search_objects: List[Dict[str, Any]], output_path: str) -> None:
    """Save the search objects to a JSON file."""
    try:
        with open(output_path, 'w') as file:
            json.dump(search_objects, file, indent=2)
        logger.info(f"Output saved to {output_path}")
    except Exception as e:
        logger.error(f"Error saving output: {e}")

def main():
    # Hardcoded configuration values
    INPUT_FILE = "companies.json"
    OUTPUT_FILE = "search_agent/search_results.json"
    MODEL = "gpt-4.1-nano"
    TIMESPAN = "last_month"  # Changed from "last_7_days" to increase search window
    BATCH_SIZE = 10
    BATCH_DELAY = 5.0
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    COUNTRY_RESTRICT = None  # Only used as fallback if company has no country attribute
    
    # Set log level to INFO
    logger.setLevel(logging.INFO)
    
    print(f"Starting company search query generator...")
    print(f"Reading company data from: {INPUT_FILE}")
    print(f"Using model: {MODEL}")
    
    # Get the API key from .env file
    api_key = os.environ.get("1OPENAI_API_KEY")
    if not api_key:
        logger.error("API key not found in .env file. Make sure OPENAI_API_KEY is set in your .env file.")
        return
    
    # Load companies
    companies = load_companies(INPUT_FILE)
    if not companies:
        logger.error("No valid companies found in companies.json. Exiting.")
        return
    
    print(f"Found {len(companies)} companies to process")
    
    # Initialize the search query generator
    generator = SearchQueryGenerator(
        api_key=api_key,
        model=MODEL,
        max_retries=MAX_RETRIES,
        retry_delay=RETRY_DELAY
    )
    
    # Process the companies in batches
    search_objects = batch_process_companies(
        companies=companies,
        generator=generator,
        batch_size=BATCH_SIZE,
        delay_between_batches=BATCH_DELAY,
        timespan=TIMESPAN,
        country_restrict=COUNTRY_RESTRICT
    )
    
    # Save the output
    save_output(search_objects, OUTPUT_FILE)
    
    # Print a sample of the generated queries
    if search_objects:
        print("\nSample of generated search queries:")
        sample_size = min(3, len(search_objects))
        for i, obj in enumerate(search_objects[:sample_size]):
            print(f"{i+1}. Company ID: {obj['company_id']}")
            print(f"   Query: {obj['search_query']}")
            print(f"   Parameters: {obj['parameters']}")
            print()
        
        print(f"Successfully generated {len(search_objects)} search queries")
        print(f"Results saved to: {OUTPUT_FILE}")
    else:
        print("No search queries were generated. Check logs for errors.")

if __name__ == "__main__":
    # Simple script banner
    print("\n" + "="*60)
    print(" Company Search Query Generator with GPT-4.1-nano ".center(60, "="))
    print("="*60 + "\n")
    
    try:
        main()
        print("\nScript completed successfully.")
    except Exception as e:
        print(f"\nError: {e}")
        print("Script execution failed. Check the logs for details.")
    
    print("\nNote: Make sure you have:")
    print("  1. A valid 'companies.json' file in the current directory")
    print("  2. A .env file with OPENAI_API_KEY=your_api_key")
    print("  3. Sufficient API credits for GPT-4.1-nano model usage")