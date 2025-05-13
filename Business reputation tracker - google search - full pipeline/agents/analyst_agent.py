import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from data.pipeline_db_config import SessionLocal
from data.pipeline_db_models import AnalysisResult, CleanedContent, ScrapedContent, SearchResult
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class AnalystAgent:
    def __init__(self):
        """Initialize the analyst agent that processes company data and generates analysis."""
        self.api_key = os.getenv("1OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
    
    def get_company_data(self):
        """Get all companies' data from the database."""
        session = SessionLocal()
        try:
            # Get all cleaned content that hasn't been analyzed yet
            cleaned_contents = session.query(CleanedContent).filter(
                ~CleanedContent.analysis_results.any()
            ).all()
            
            company_data_list = []
            for cleaned_content in cleaned_contents:
                # Check if analysis already exists for this cleaned content
                existing_analysis = session.query(AnalysisResult).filter(
                    AnalysisResult.cleaned_content_id == cleaned_content.id
                ).first()
                
                if existing_analysis:
                    logger.debug(f"Skipping duplicate analysis for cleaned content ID {cleaned_content.id}")
                    continue
                
                # Get the associated scraped content and search result
                scraped_content = cleaned_content.scraped_content
                search_result = scraped_content.search_result
                
                # Extract industry and other metadata from the search result's raw_json
                raw_json = search_result.raw_json or {}
                metadata = raw_json.get('metadata', {})
                
                # Create company data structure
                company_data = {
                    "company_id": str(cleaned_content.id),
                    "company_name": search_result.company_name,
                    "industry": metadata.get('industry', 'Unknown'),
                    "location": metadata.get('location', 'Unknown'),
                    "description": metadata.get('description', ''),
                    "services": metadata.get('services', []),
                    "content_items": [{
                        "url": search_result.link,
                        "title": search_result.title,
                        "domain": scraped_content.domain,
                        "publication_date": search_result.published_date.isoformat() if search_result.published_date else None,
                        "meta_description": search_result.snippet,
                        "cleaned_content": cleaned_content.cleaned_text
                    }]
                }
                company_data_list.append(company_data)
            
            return company_data_list
        except Exception as e:
            logger.error(f"Error getting company data: {e}")
            raise
        finally:
            session.close()
    
    def analyze_company(self, company_data):
        """Analyze company data using GPT-4.1 Nano and generate insights with sentiment for each webpage."""
        # Extract company information
        company_info = {
            "company_id": company_data.get("company_id", ""),
            "company_name": company_data.get("company_name", ""),
            "industry": company_data.get("industry", "Unknown"),
            "location": company_data.get("location", "Unknown"),
            "description": company_data.get("description", ""),
            "services": company_data.get("services", []),
            "content_items": company_data.get("content_items", [])
        }
        
        # Create the overall company analysis
        company_analysis = self._analyze_overall_company(company_info, company_data.get("content_items", []))
        
        # Analyze each content item separately
        content_analyses = []
        for item in company_data.get("content_items", []):
            content_analysis = self._analyze_content_item(company_info, item)
            content_analyses.append(content_analysis)
        
        # Create complete analysis result
        analysis_result = {
            "company_id": company_info["company_id"],
            "company_name": company_info["company_name"],
            "analysis_timestamp": datetime.now().isoformat(),
            "overall_analysis": company_analysis,
            "content_analyses": content_analyses
        }
        
        return analysis_result
    
    def _analyze_overall_company(self, company_info, content_items):
        """Generate overall company analysis."""
        # Create prompt for overall company analysis
        prompt = f"""
        Analyze the following company:
        
        Company Information:
        - Company ID: {company_info['company_id']}
        - Company Name: {company_info['company_name']}
        - Industry: {company_info['industry']}
        - Location: {company_info['location']}
        - Description: {company_info['description']}
        - Services: {', '.join(company_info['services'])}
        
        The company has {len(content_items)} content items from its web presence.
        
        Based on this information, provide a brief overall analysis of the company that includes:
        1. Market positioning
        2. Business focus
        3. Overall sentiment analysis
        
        For the sentiment analysis, you MUST include:
        - A numerical score between -1.0 (very negative) and 1.0 (very positive), with 0.0 being neutral
        - A sentiment label (positive, neutral, or negative)
        - A brief explanation of the sentiment assessment
        
        Include a dedicated "SENTIMENT ANALYSIS" section at the end with this format:
        SENTIMENT ANALYSIS:
        Score: [numerical value between -1.0 and 1.0]
        Label: [positive/neutral/negative]
        Explanation: [brief explanation]
        """
        
        # Call GPT-4.1 Nano for overall analysis
        analysis_text = self._call_gpt(prompt)
        
        # Extract sentiment directly from GPT for reliability
        sentiment = self._get_direct_sentiment(company_info, content_items)
        
        return {
            "analysis_text": analysis_text,
            "sentiment": sentiment
        }
    
    def _analyze_content_item(self, company_info, content_item):
        """Analyze an individual content item (webpage) and generate insights with sentiment."""
        # Extract content item information
        url = content_item.get("url", "")
        title = content_item.get("title", "")
        domain = content_item.get("domain", "")
        publication_date = content_item.get("publication_date", "")
        meta_description = content_item.get("meta_description", "")
        cleaned_content = content_item.get("cleaned_content", "")
        
        # Generate summary
        summary = self._generate_summary(content_item)
        
        # Limit content length for API
        max_content_length = 1500
        if len(cleaned_content) > max_content_length:
            cleaned_content = cleaned_content[:max_content_length] + "..."
        
        # Create prompt for content analysis
        prompt = f"""
        Analyze the following webpage content for {company_info['company_name']} ({company_info['company_id']}):
        
        URL: {url}
        Title: {title}
        Domain: {domain}
        Publication Date: {publication_date}
        Meta Description: {meta_description}
        
        Content:
        {cleaned_content}
        
        Provide a brief analysis of this content that includes:
        1. Key themes or topics
        2. Notable information or developments
        """
        
        # Call GPT-4.1 Nano for content analysis
        analysis_text = self._call_gpt(prompt)
        
        # Get sentiment directly using a dedicated sentiment call
        sentiment = self._get_content_sentiment(content_item)
        
        return {
            "url": url,
            "title": title,
            "summary": summary,
            "analysis_text": analysis_text,
            "sentiment": sentiment
        }
    
    def _get_direct_sentiment(self, company_info, content_items):
        """Get sentiment directly using a dedicated sentiment-focused call."""
        # Create a simple description for sentiment analysis
        company_description = f"""{company_info['company_name']} is a {company_info['industry']} company based in {company_info['location']}. 
        {company_info['description']}
        Services: {', '.join(company_info['services'])}"""
        
        # Create a focused sentiment prompt
        prompt = f"""
        Analyze the sentiment for the following company:
        
        {company_description}
        
        Respond ONLY with a JSON object that has these three fields:
        1. "score": a numerical value between -1.0 (very negative) and 1.0 (very positive), with 0.0 being neutral
        2. "label": one of "positive", "neutral", or "negative"
        3. "explanation": a brief explanation of your sentiment assessment
        
        IMPORTANT: Return ONLY a valid JSON object with these fields. Do not include any other text.
        """
        
        # Call GPT for sentiment
        response = self._call_gpt(prompt)
        
        try:
            # Try to parse as JSON
            sentiment = json.loads(response)
            # Ensure the expected fields exist
            if not all(key in sentiment for key in ["score", "label", "explanation"]):
                # If missing keys, create default sentiment
                return self._create_default_sentiment(response)
            return sentiment
        except json.JSONDecodeError:
            # If not valid JSON, create default sentiment
            return self._create_default_sentiment(response)
    
    def _get_content_sentiment(self, content_item):
        """Get sentiment for a specific content item using a dedicated sentiment analysis."""
        url = content_item.get("url", "")
        title = content_item.get("title", "")
        cleaned_content = content_item.get("cleaned_content", "")
        
        # Limit content length
        if len(cleaned_content) > 1000:
            cleaned_content = cleaned_content[:1000] + "..."
        
        # Create a focused sentiment prompt
        prompt = f"""
        Analyze the sentiment of this webpage content:
        
        URL: {url}
        Title: {title}
        
        Content:
        {cleaned_content}
        
        Respond ONLY with a JSON object that has these three fields:
        1. "score": a numerical value between -1.0 (very negative) and 1.0 (very positive), with 0.0 being neutral
        2. "label": one of "positive", "neutral", or "negative"
        3. "explanation": a brief explanation of your sentiment assessment
        
        IMPORTANT: Return ONLY a valid JSON object with these fields. Do not include any other text.
        """
        
        # Call GPT for sentiment
        response = self._call_gpt(prompt)
        
        try:
            # Try to parse as JSON
            sentiment = json.loads(response)
            # Ensure the expected fields exist
            if not all(key in sentiment for key in ["score", "label", "explanation"]):
                # If missing keys, create default sentiment
                return self._create_default_sentiment(response)
            return sentiment
        except json.JSONDecodeError:
            # If not valid JSON, create default sentiment
            return self._create_default_sentiment(response)
    
    def _create_default_sentiment(self, text):
        """Create a default sentiment object based on text analysis."""
        import re
        
        # Default values
        sentiment_score = 0.0
        sentiment_label = "neutral"
        
        # Try to extract score from text
        score_match = re.search(r'(?:score|sentiment):\s*([-+]?\d+\.\d+)', text, re.IGNORECASE)
        if score_match:
            try:
                sentiment_score = float(score_match.group(1))
                sentiment_label = "positive" if sentiment_score > 0.2 else "negative" if sentiment_score < -0.2 else "neutral"
            except ValueError:
                pass
        
        # Try to find sentiment label if score was not found
        if sentiment_score == 0.0:
            if re.search(r'\bpositive\b', text, re.IGNORECASE):
                sentiment_score = 0.7
                sentiment_label = "positive"
            elif re.search(r'\bnegative\b', text, re.IGNORECASE):
                sentiment_score = -0.7
                sentiment_label = "negative"
            elif re.search(r'\bneutral\b', text, re.IGNORECASE):
                sentiment_score = 0.0
                sentiment_label = "neutral"
        
        # If still no sentiment found, make one more attempt with a focused API call
        if sentiment_score == 0.0 and not re.search(r'\bneutral\b', text, re.IGNORECASE):
            # Make one more attempt with even more direct prompt
            retry_prompt = f"Based on this text, provide ONLY a sentiment score between -1.0 and 1.0:\n\n{text}"
            retry_response = self._call_gpt(retry_prompt)
            
            # Try to find a number in the response
            number_match = re.search(r'([-+]?\d+\.\d+)', retry_response)
            if number_match:
                try:
                    sentiment_score = float(number_match.group(1))
                    sentiment_label = "positive" if sentiment_score > 0.2 else "negative" if sentiment_score < -0.2 else "neutral"
                except ValueError:
                    pass
        
        return {
            "score": sentiment_score,
            "label": sentiment_label,
            "explanation": text
        }
    
    def _call_gpt(self, prompt):
        """Call GPT-4.1 Nano with the given prompt."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": "gpt-4.1-nano",
            "messages": [
                {"role": "system", "content": "You are an expert financial and business analyst. Provide insightful analysis with objective sentiment assessment."},
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"API call failed with status code {response.status_code}: {response.text}")
        
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]
    
    def save_analysis(self, analysis_result):
        """Save analysis result to the database."""
        session = SessionLocal()
        try:
            # Get the cleaned content record
            cleaned_content = session.query(CleanedContent).filter(
                CleanedContent.id == analysis_result["company_id"]
            ).first()
            
            if not cleaned_content:
                raise ValueError(f"No cleaned content found for company ID {analysis_result['company_id']}")
            
            # Create analysis result record
            analysis = AnalysisResult(
                cleaned_content_id=cleaned_content.id,
                sentiment_score=analysis_result["overall_analysis"]["sentiment"]["score"],
                sentiment_label=analysis_result["overall_analysis"]["sentiment"]["label"],
                analysis_text=analysis_result["overall_analysis"]["analysis_text"],
                summary=analysis_result["content_analyses"][0]["summary"] if analysis_result["content_analyses"] else None
            )
            
            session.add(analysis)
            session.commit()
            
            return analysis.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def run_analysis(self):
        """Run analysis on all company data from the database."""
        company_data_list = self.get_company_data()
        analysis_results = []
        
        for company_data in company_data_list:
            try:
                print(f"Analyzing company: {company_data['company_name']}...")
                analysis_result = self.analyze_company(company_data)
                analysis_id = self.save_analysis(analysis_result)
                analysis_results.append(analysis_result)
                print(f"Analysis saved to database with ID: {analysis_id}")
            except Exception as e:
                print(f"Error analyzing company {company_data['company_name']}: {str(e)}")
        
        return analysis_results

    def _generate_summary(self, content_item):
        """Generate a 3-sentence summary of the cleaned content using GPT-4.1 Nano."""
        cleaned_content = content_item.get("cleaned_content", "")
        
        # Limit content length for API
        max_content_length = 1500
        if len(cleaned_content) > max_content_length:
            cleaned_content = cleaned_content[:max_content_length] + "..."
        
        prompt = f"""
        Summarize the following content in exactly 3 sentences. Focus on the key points and main message:

        {cleaned_content}

        Provide ONLY the 3-sentence summary. Do not include any additional text or explanations.
        """
        
        return self._call_gpt(prompt)

def main():
    """Main function to run the analyst agent."""
    analyst = AnalystAgent()
    analysis_results = analyst.run_analysis()
    
    # Print summary
    print(f"\nAnalyzed {len(analysis_results)} companies:")
    for result in analysis_results:
        print(f"- {result['company_name']} (overall sentiment: {result['overall_analysis']['sentiment']['label']} {result['overall_analysis']['sentiment']['score']})")
        print("  Webpage sentiments:")
        for content in result["content_analyses"]:
            print(f"  - {content['title'][:40]}...: {content['sentiment']['label']} ({content['sentiment']['score']})")

if __name__ == "__main__":
    main()