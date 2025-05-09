import os
import json
from datetime import datetime, UTC
from openai import OpenAI
from dotenv import load_dotenv
import time

class SentimentAnalyzer:
    def __init__(self):
        """Initialize the sentiment analyzer with OpenAI client."""
        load_dotenv()
        api_key = os.getenv("1OPENAI_API_KEY")  # Fixed API key name
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = OpenAI(api_key=api_key)
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def is_valid_content(self, item):
        """Check if an item has valid content for analysis.
        
        Args:
            item (dict): The item to validate
            
        Returns:
            bool: True if the item has valid content, False otherwise
        """
        # Check if item is a dictionary
        if not isinstance(item, dict):
            return False
            
        # Get content and check if it's a non-empty string
        content = item.get('content', '')
        if not isinstance(content, str) or not content.strip():
            return False
            
        # Check if content is too short (less than 10 characters)
        if len(content.strip()) < 10:
            return False
            
        return True
    
    def analyze_content(self, cleaned_content, entities=None):
        """Analyze sentiment of cleaned content using OpenAI API.
        
        Args:
            cleaned_content (str): The cleaned content to analyze
            entities (list, optional): List of known entities in the content
            
        Returns:
            dict: Analysis results including sentiment score, reason, topics, and reputation impact
        """
        # Clean and prepare content
        cleaned_content = cleaned_content.strip()
        if not cleaned_content:
            return {
                'sentiment_score': 0,
                'sentiment_reason': 'Empty content provided',
                'key_topics': [],
                'reputation_impact': 'No impact analysis possible',
                'analyzed_at': datetime.now(UTC).isoformat()
            }
        
        # Truncate content if it's too long (approximately 4000 tokens)
        max_chars = 16000  # Rough estimate for 4000 tokens
        if len(cleaned_content) > max_chars:
            cleaned_content = cleaned_content[:max_chars] + "... [content truncated]"
        
        for attempt in range(self.max_retries):
            try:
                # Prepare system message with clear instructions
                system_message = """You are a sentiment and reputation analysis assistant. Analyze the provided content and return a JSON object with the following structure:
                {
                    "sentiment_score": integer from -10 to 10,
                    "sentiment_reason": "Detailed explanation of the score",
                    "key_topics": ["List of main topics discussed"],
                    "reputation_impact": "Analysis of how this content affects company reputation"
                }
                
                Sentiment score guidelines:
                - -10 to -7: Extremely negative (severe criticism, scandal, major failure)
                - -6 to -3: Moderately negative (problems, challenges, disappointment)
                - -2 to -1: Slightly negative (minor issues, concerns)
                - 0: Neutral (factual reporting, balanced view)
                - 1 to 2: Slightly positive (minor achievements, small improvements)
                - 3 to 6: Moderately positive (success, growth, good performance)
                - 7 to 10: Extremely positive (major achievement, breakthrough, exceptional success)"""

                # Prepare user message with content and known entities
                user_message = f"""Please analyze the following content for sentiment and reputation impact.
Known entities in the content: {', '.join(entities) if entities else 'None provided'}

Content to analyze:
{cleaned_content}

Provide a thorough analysis focusing on:
1. Overall sentiment and specific reasons for the score
2. Key topics discussed in the content
3. How this content might impact the company's reputation
4. Any notable claims, achievements, or criticisms

Return your analysis in the specified JSON format."""

                # Make the API call
                response = self.client.chat.completions.create(
                    model="gpt-4.1-mini",  # Using standard GPT-4.1
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3
                )
                
                # Parse and validate the response
                result = json.loads(response.choices[0].message.content)
                
                # Validate sentiment score range
                score = int(result['sentiment_score'])
                if not -10 <= score <= 10:
                    score = 0  # Default to neutral if invalid
                
                return {
                    'sentiment_score': score,
                    'sentiment_reason': result.get('sentiment_reason', 'No reason provided'),
                    'key_topics': result.get('key_topics', []),
                    'reputation_impact': result.get('reputation_impact', 'No impact analysis provided'),
                    'analyzed_at': datetime.now(UTC).isoformat()
                }
                
            except Exception as e:
                if "rate_limit_exceeded" in str(e):
                    if attempt < self.max_retries - 1:
                        print(f"Rate limit exceeded, retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)
                        continue
                print(f"Error in sentiment analysis: {str(e)}")
                return {
                    'sentiment_score': 0,
                    'sentiment_reason': f"Error in analysis: {str(e)}",
                    'key_topics': [],
                    'reputation_impact': 'Analysis failed',
                    'analyzed_at': datetime.now(UTC).isoformat()
                }

    def process_files(self, input_dir='web_scraping_agent/cleaned_results', output_dir='LLM_sentiment_agent/analyzed_results'):
        """Process all cleaned results files and perform sentiment analysis.
        
        Args:
            input_dir (str): Directory containing cleaned results files
            output_dir (str): Directory to save analyzed results
        """
        # Normalize paths
        input_dir = os.path.normpath(input_dir)
        output_dir = os.path.normpath(output_dir)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get all cleaned results files
        cleaned_files = [f for f in os.listdir(input_dir) if f.startswith('cleaned_results_') and f.endswith('.json')]
        
        if not cleaned_files:
            print(f"No cleaned results files found in {input_dir}")
            return
        
        # Process each file
        for filename in cleaned_files:
            try:
                file_path = os.path.join(input_dir, filename)
                print(f"\nProcessing {filename}...")
                
                # Read the cleaned content
                with open(file_path, 'r', encoding='utf-8') as f:
                    cleaned_data = json.load(f)
                
                # Generate output filename
                output_file = os.path.join(output_dir, f'analyzed_{filename}')
                
                # Process each item in the cleaned data
                analyzed_results = []
                total_items = len(cleaned_data)
                valid_items = 0
                failed_items = 0
                skipped_items = 0
                
                for index, item in enumerate(cleaned_data, 1):
                    try:
                        # Check if item has valid content
                        if not self.is_valid_content(item):
                            skipped_items += 1
                            analyzed_item = {
                                **item,
                                'sentiment_analysis': {
                                    'sentiment_score': 0,
                                    'sentiment_reason': 'Invalid or empty content',
                                    'key_topics': [],
                                    'reputation_impact': 'No impact analysis possible',
                                    'analyzed_at': datetime.now(UTC).isoformat()
                                }
                            }
                            analyzed_results.append(analyzed_item)
                            continue
                        
                        print(f"Processing item {index}/{total_items} in {filename}")
                        
                        # Extract content and entities
                        content = item.get('content', '')
                        entities = item.get('entities', [])
                        
                        # Perform sentiment analysis
                        sentiment_data = self.analyze_content(content, entities)
                        
                        # Check if analysis failed
                        if sentiment_data['sentiment_reason'].startswith('Error in analysis'):
                            failed_items += 1
                            print(f"Failed to analyze item {index}: {sentiment_data['sentiment_reason']}")
                        else:
                            valid_items += 1
                        
                        # Combine original data with sentiment analysis
                        analyzed_item = {
                            **item,
                            'sentiment_analysis': sentiment_data
                        }
                        
                        analyzed_results.append(analyzed_item)
                        
                    except Exception as e:
                        failed_items += 1
                        print(f"Error processing item {index}: {str(e)}")
                        analyzed_item = {
                            **item,
                            'sentiment_analysis': {
                                'sentiment_score': 0,
                                'sentiment_reason': f'Error processing item: {str(e)}',
                                'key_topics': [],
                                'reputation_impact': 'Analysis failed',
                                'analyzed_at': datetime.now(UTC).isoformat()
                            }
                        }
                        analyzed_results.append(analyzed_item)
                
                # Save the analyzed results
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(analyzed_results, f, indent=2, ensure_ascii=False)
                
                print(f"\nSummary for {filename}:")
                print(f"Total items: {total_items}")
                print(f"Successfully analyzed: {valid_items}")
                print(f"Failed to analyze: {failed_items}")
                print(f"Skipped (invalid/empty): {skipped_items}")
                print(f"Results saved to {output_file}")
                
            except Exception as e:
                print(f"Error processing file {filename}: {str(e)}")
                continue

if __name__ == "__main__":
    try:
        # Example usage
        analyzer = SentimentAnalyzer()
        
        # Process all files in the default directories
        analyzer.process_files()
        
        # Example of analyzing a single piece of content
        sample_content = "This is a sample content for testing sentiment analysis."
        result = analyzer.analyze_content(sample_content)
        print("\nSample analysis result:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"Fatal error: {str(e)}") 