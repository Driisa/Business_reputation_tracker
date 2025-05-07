import os
import sys
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.database import CleanedContent, SentimentAnalysis, get_db_session

class SentimentAnalyzer:
    def __init__(self):
        """Initialize the sentiment analyzer with OpenAI client and database session."""
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("1OPENAI_API_KEY"))
        self.db = get_db_session()
    
    def analyze_all_content(self):
        """Analyze sentiment for all cleaned content that hasn't been analyzed yet."""
        # Get all cleaned content that doesn't have sentiment analysis
        cleaned_contents = self.db.query(CleanedContent).outerjoin(SentimentAnalysis).filter(SentimentAnalysis.id == None).all()
        
        print(f"Found {len(cleaned_contents)} articles to analyze")
        
        for cleaned_content in cleaned_contents:
            try:
                print(f"Analyzing sentiment for content ID: {cleaned_content.id}")
                
                # Get the LLM cleaned content
                content_to_analyze = cleaned_content.llm_cleaned_content
                
                # Get any existing metadata about entities
                metadata = json.loads(cleaned_content.cleaning_metadata) if cleaned_content.cleaning_metadata else {}
                entities = metadata.get('entities', [])
                
                # Perform sentiment analysis
                sentiment_data = self._analyze_sentiment(content_to_analyze, entities)
                
                # Create sentiment analysis entry
                sentiment_analysis = SentimentAnalysis(
                    cleaned_content_id=cleaned_content.id,
                    sentiment_score=sentiment_data['sentiment_score'],
                    sentiment_reason=sentiment_data['sentiment_reason'],
                    key_topics=json.dumps(sentiment_data['key_topics']),
                    reputation_impact=sentiment_data['reputation_impact']
                )
                
                self.db.add(sentiment_analysis)
                self.db.commit()
                
                print(f"Sentiment analysis completed for ID {cleaned_content.id}:")
                print(f"- Score: {sentiment_data['sentiment_score']}")
                print(f"- Topics: {len(sentiment_data['key_topics'])}")
                
            except Exception as e:
                print(f"Error analyzing content ID {cleaned_content.id}: {str(e)}")
                self.db.rollback()
                continue
        
        return self._get_all_analysis_results()
    
    def _analyze_sentiment(self, content, known_entities):
        """Analyze sentiment of content using OpenAI API."""
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
Known entities in the content: {', '.join(known_entities)}

Content to analyze:
{content}

Provide a thorough analysis focusing on:
1. Overall sentiment and specific reasons for the score
2. Key topics discussed in the content
3. How this content might impact the company's reputation
4. Any notable claims, achievements, or criticisms

Return your analysis in the specified JSON format."""

            # Make the API call
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
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
                'reputation_impact': result.get('reputation_impact', 'No impact analysis provided')
            }
            
        except Exception as e:
            print(f"Error in sentiment analysis: {str(e)}")
            return {
                'sentiment_score': 0,
                'sentiment_reason': f"Error in analysis: {str(e)}",
                'key_topics': [],
                'reputation_impact': 'Analysis failed'
            }
    
    def _get_all_analysis_results(self):
        """Retrieve all sentiment analysis results from the database."""
        try:
            analyses = self.db.query(SentimentAnalysis).all()
            return {
                'results_count': len(analyses),
                'analyses': [
                    {
                        'id': a.id,
                        'cleaned_content_id': a.cleaned_content_id,
                        'sentiment_score': a.sentiment_score,
                        'sentiment_reason': a.sentiment_reason,
                        'key_topics': json.loads(a.key_topics) if a.key_topics else [],
                        'reputation_impact': a.reputation_impact,
                        'created_at': a.created_at.isoformat()
                    }
                    for a in analyses
                ]
            }
        except Exception as e:
            print(f"Error retrieving analysis results from database: {str(e)}")
            return {'results_count': 0, 'analyses': []}

def main():
    """Run the sentiment analyzer"""
    analyzer = SentimentAnalyzer()
    results = analyzer.analyze_all_content()
    print(f"Sentiment analysis completed. Processed {results['results_count']} articles.")

if __name__ == "__main__":
    main()