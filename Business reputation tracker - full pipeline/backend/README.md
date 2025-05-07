# Business Reputation Tracker

A comprehensive system for tracking and analyzing business reputation by searching for company mentions, scraping content, and analyzing sentiment using Large Language Models (LLM).

## Features

- 🔍 Automated company mention search using Google Custom Search API
- 📝 Web content scraping and processing
- 🤖 LLM-powered content cleaning and structuring
- 📊 Sentiment analysis and reputation impact assessment
- 🔄 Real-time database synchronization
- 📈 Historical data tracking and analysis

## Prerequisites

- Python 3.8 or higher
- Google Custom Search API credentials
- OpenAI API credentials
- SQLite (included with Python)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd business-reputation-tracker
```

2. Create and activate a virtual environment (recommended):
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/MacOS
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following variables:
```env
# Google Custom Search API credentials
GOOGLE_SEARCH_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here

# OpenAI API credentials
OPENAI_API_KEY=your_openai_api_key_here
```

5. Add companies to track in `backend/agents/companies.json`:
```json
[
    "Company Name 1",
    "Company Name 2",
    "Company Name 3"
]
```

## Project Structure

```
backend/
├── agents/                 # Pipeline agents
│   ├── company_search_agent.py
│   ├── web_scraping_agent.py
│   ├── LLM_cleaning_agent.py
│   └── LLM_sentiment_agent.py
├── app/                   # FastAPI application
│   ├── app.py
│   ├── database.py
│   └── frontend_database.py
├── data/                  # Data storage
├── scripts/              # Utility scripts
└── run_pipeline.py       # Main pipeline runner
```

## Usage

### Running the Backend

1. Initialize/Clean the database:
```bash
python backend/scripts/clean_database.py
```

2. Start the FastAPI backend server:
```bash
# Option 1: Using Python module path (recommended)
python -m backend.app.app

# Option 2: Using uvicorn directly
cd backend
uvicorn app:app --reload --port 8000
```

The backend will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative API Documentation: http://localhost:8000/redoc

### Running the Pipeline

To run the complete pipeline (search, scrape, clean, and analyze):
```bash
python -m backend.run_pipeline
```

Or run individual agents:
```bash
# Search for company mentions
python backend/agents/company_search.py

# Scrape content from search results
python backend/agents/web_scraping_agent.py

# Clean and structure content
python backend/agents/LLM_Cleaning_agent.py

# Analyze sentiment and reputation
python backend/agents/LLM_sentiment_agent.py
```

## Database Schema

The system uses SQLite with SQLAlchemy ORM. The database file `Objekt storage.db` will be created automatically in `backend/data/` when you first run the pipeline.

### Tables

- `Company`: Stores company information
  - id: Integer (Primary Key)
  - name: String
  - description: Text
  - created_at: DateTime
  - updated_at: DateTime

- `SearchResult`: Stores search results
  - id: Integer (Primary Key)
  - company_id: Integer (Foreign Key)
  - query: String
  - url: String
  - title: String
  - snippet: Text
  - created_at: DateTime

- `ScrapedContent`: Stores raw scraped content
  - id: Integer (Primary Key)
  - search_result_id: Integer (Foreign Key)
  - content: Text
  - created_at: DateTime

- `CleanedContent`: Stores processed content
  - id: Integer (Primary Key)
  - scraped_content_id: Integer (Foreign Key)
  - basic_cleaned_content: Text
  - llm_cleaned_content: Text
  - cleaning_metadata: JSON
  - created_at: DateTime

- `SentimentAnalysis`: Stores sentiment and reputation analysis
  - id: Integer (Primary Key)
  - cleaned_content_id: Integer (Foreign Key)
  - sentiment_score: Float
  - sentiment_reason: Text
  - key_topics: JSON
  - reputation_impact: Text
  - created_at: DateTime

## Development

### Code Style

This project follows PEP 8 style guidelines. Before committing, ensure your code is properly formatted:

```bash
# Install development dependencies
pip install black flake8

# Format code
black .

# Check code style
flake8
```

### Testing

Run tests using pytest:
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest

# Run tests with coverage
pytest --cov=backend
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]

## Support

For support, please [add contact information or issue reporting guidelines] 