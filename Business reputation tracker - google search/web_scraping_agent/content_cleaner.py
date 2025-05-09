import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
import html
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("content_cleaning.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("content_cleaner")

def get_processed_files():
    """Get list of already processed files"""
    script_dir = Path(__file__).parent.parent
    processed_file = script_dir / 'web_scraping_agent' / 'cleaned_files.json'
    
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
    processed_file = script_dir / 'web_scraping_agent' / 'cleaned_files.json'
    
    processed_files = get_processed_files()
    processed_files.add(filename)
    
    with open(processed_file, 'w', encoding='utf-8') as f:
        json.dump(list(processed_files), f)

class ContentCleaner:
    def __init__(self):
        # Initialize OpenAI client
        self.client = OpenAI(api_key=os.getenv('1OPENAI_API_KEY'))
        
        # Common HTML entities and their replacements
        self.html_entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&cent;': '¢',
            '&pound;': '£',
            '&euro;': '€',
            '&copy;': '©',
            '&reg;': '®'
        }
        
        # Common irrelevant text patterns
        self.irrelevant_patterns = [
            r'cookie policy',
            r'privacy policy',
            r'terms of service',
            r'terms and conditions',
            r'© \d{4}',
            r'all rights reserved',
            r'click here',
            r'read more',
            r'subscribe',
            r'sign up',
            r'newsletter',
            r'follow us',
            r'share this',
            r'related articles',
            r'related posts',
            r'popular posts',
            r'recent posts',
            r'categories',
            r'tags',
            r'comments',
            r'leave a comment',
            r'search',
            r'menu',
            r'home',
            r'about',
            r'contact',
            r'login',
            r'register',
            r'sign in',
            r'log in',
            r'create account',
            r'forgot password',
            r'reset password',
            r'change password',
            r'profile',
            r'settings',
            r'account',
            r'cart',
            r'checkout',
            r'wishlist',
            r'favorites',
            r'saved items',
            r'recently viewed',
            r'you may also like',
            r'recommended for you',
            r'sponsored',
            r'advertisement',
            r'ad',
            r'sponsored content',
            r'promoted',
            r'promotion',
            r'deal',
            r'offer',
            r'discount',
            r'sale',
            r'clearance',
            r'free shipping',
            r'free delivery',
            r'free returns',
            r'free trial',
            r'free sample',
            r'free gift',
            r'free download',
            r'free access',
            r'free account',
            r'free membership',
            r'free subscription',
            r'free service',
            r'free tool',
            r'free app',
            r'free software',
            r'free program',
            r'free course',
            r'free class',
            r'free workshop',
            r'free webinar',
            r'free event',
            r'free consultation',
            r'free assessment',
            r'free evaluation',
            r'free analysis',
            r'free report',
            r'free guide',
            r'free ebook',
            r'free whitepaper',
            r'free case study',
            r'free infographic',
            r'free video',
            r'free podcast',
            r'free newsletter',
            r'free blog',
            r'free article',
            r'free content',
            r'free resource',
            r'free material',
            r'free information',
            r'free data',
            r'free statistics',
            r'free research',
            r'free study',
            r'free survey',
            r'free poll',
            r'free quiz',
            r'free test',
            r'free assessment',
            r'free evaluation',
            r'free analysis',
            r'free report',
            r'free guide',
            r'free ebook',
            r'free whitepaper',
            r'free case study',
            r'free infographic',
            r'free video',
            r'free podcast',
            r'free newsletter',
            r'free blog',
            r'free article',
            r'free content',
            r'free resource',
            r'free material',
            r'free information',
            r'free data',
            r'free statistics',
            r'free research',
            r'free study',
            r'free survey',
            r'free poll',
            r'free quiz',
            r'free test'
        ]
        
        # Compile regex patterns
        self.irrelevant_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.irrelevant_patterns]

    def clean_content_with_llm(self, content: str) -> str:
        """
        Use LLM to further clean and improve the content after initial cleaning.
        
        Args:
            content (str): The initially cleaned content
            
        Returns:
            str: The LLM-cleaned content
        """
        try:
            system_message = """You are a content cleaning assistant. Your task is to:
1. Remove any remaining irrelevant content, ads, or boilerplate text
2. Fix any formatting issues or inconsistencies
3. Preserve the main message and important information
4. Make the text more concise while maintaining clarity
5. Remove any duplicate information
6. Fix any grammatical errors or awkward phrasing

Return only the cleaned content without any explanations or additional text."""

            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": content}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error in LLM cleaning: {str(e)}")
            return content  # Return original content if LLM cleaning fails

    def clean_content(self, content: str) -> str:
        """
        Clean the content using both pattern-based and LLM-based cleaning.
        
        Args:
            content (str): The raw content to clean
            
        Returns:
            str: The cleaned content
        """
        if not content:
            return ""
            
        # Initial cleaning with patterns
        content = html.unescape(content)
        soup = BeautifulSoup(content, 'html.parser')
        content = soup.get_text()
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        for pattern in self.irrelevant_patterns:
            content = pattern.sub('', content)
            
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        # If content is too short after initial cleaning, return as is
        if len(content.split()) < 10:
            return content
            
        # Apply LLM-based cleaning
        return self.clean_content_with_llm(content)

    def clean_scraped_results(self, company_name: str) -> None:
        """
        Clean all scraped results for a company.
        
        Args:
            company_name (str): The name of the company
        """
        script_dir = Path(__file__).parent
        input_dir = script_dir / 'scraped_results'
        output_dir = script_dir / 'cleaned_results'
        output_dir.mkdir(exist_ok=True)
        
        # Get current date for filename
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        input_file = input_dir / f"scraped_results_{company_name.lower()}_{current_date}.json"
        if not input_file.exists():
            logger.error(f"Scraped results not found for {company_name} on {current_date}")
            return
            
        # Check if this file has already been processed
        if str(input_file) in get_processed_files():
            logger.info(f"File {input_file} has already been cleaned. Skipping.")
            return
            
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                scraped_results = json.load(f)
                
            cleaned_results = []
            for result in scraped_results:
                cleaned_content = self.clean_content(result['content'])
                
                cleaned_result = {
                    'title': result['title'],
                    'url': result['url'],
                    'content': cleaned_content,
                    'published_date': result['published_date'],
                    'type': result['type'],
                    'valid': result['valid']
                }
                
                cleaned_results.append(cleaned_result)
                
            # Save cleaned results with date in filename
            output_file = output_dir / f"cleaned_results_{company_name.lower()}_{current_date}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_results, f, indent=2, ensure_ascii=False)
                
            # Mark this file as processed
            save_processed_file(str(input_file))
                
            logger.info(f"Cleaned results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error cleaning results for {company_name}: {str(e)}")

def main():
    """Main function to clean scraped results for all companies."""
    # Get list of companies from companies.json
    script_dir = Path(__file__).parent.parent
    companies_file = script_dir / 'perplexica_search_agent' / 'companies.json'
    
    try:
        with open(companies_file, 'r', encoding='utf-8') as f:
            companies_data = json.load(f)
            
        cleaner = ContentCleaner()
        
        for company in companies_data['companies']:
            company_name = company['name']
            logger.info(f"Cleaning results for {company_name}")
            cleaner.clean_scraped_results(company_name)
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main() 