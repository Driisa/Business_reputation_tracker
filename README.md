# Company Mentioning Tracker: Automated MLOps Pipeline for Real-Time Sentiment Monitoring

This repository hosts the "Company Mentioning Tracker," An Automated Pipeline for Mentioning Monitoring Across Wed Sources. It uses open-source technologies and modern APIs to offer a transparent, scalable, and cost-effective solution for reputation management.

## Features

- **Automated Data Ingestion**: Systematically acquires relevant online content from news media for target companies.
- **Sentiment Analysis**: Utilizes Large Language Models (LLMs) to classify sentiment and extract rationale from news articles.
- **Modular Pipeline**: Features an agent-based architecture for scalability, maintainability, and robust execution.
- **Data Processing**: Includes cleaning and validation to transform raw content into structured, normalized text.
- **Historical Trend Tracking**: Stores mentions in a structured database to track trends over time.
- **User Interface (UI) & API Access**: Provides a dashboard for visual sentiment overview and an API for integration with BI tools.

## System Architecture

The pipeline consists of modular agents for distinct tasks:

**Ingest**: 
- `intelligent_search_agent.py` (queries Google Custom Search API)
- `web_scraping_agent.py` (uses BeautifulSoup to fetch and extract content)

**Process**: 
- `cleaning_validation_agent.py` (cleans and normalizes text)
- `analyst_agent.py` (performs sentiment analysis using LLMs)

**Store**: 
- `SQL_intermediate.db` (for intermediate data)
- `SQL_to_frontend.db` (frontend-ready data)
- `registered companies.db` (registered companies)

**Orchestration**: 
- `run_pipeline.py` coordinates the agents.

## Repository Structure

```
.
├── UI/
│   ├── app.py
│   └── requirements.txt
├── agents/
│   ├── __pycache__/
│   ├── __init__.py
│   ├── analyst_agent.py             # Performs sentiment analysis
│   ├── cleaning_validation_agent.py # Cleans and normalizes text
│   ├── intelligent_search_agent.py  # Queries Google Search API
│   └── web_scraping_agent.py        # Scrapes web content
├── data/
│   └── __pycache__/
├── database/
│   ├── companies.db - (registered companies.db)                 # Stores company information
│   ├── object_store.db - (SQL_intermediate.db)              # Intermediate data storage
│   ├── to_frontend.db - (SQL_to_frontend.db)               # Data for frontend display
│   ├── __init__.py
│   ├── company_repository.py
│   ├── database_objekt_store.py
│   ├── frontend_db_sync.py          # Syncs data to frontend DB
│   ├── init_companies_db.py
│   ├── init_object_store.py
│   ├── pipeline_db_config.py
│   └── pipeline_db_models.py
├── logs/                            # Contains system logs
│   ├── pipeline_20250521_105317.log
│   ├── pipeline_20250521_105542.log
│   └── pipeline_20250521_105543.log
├── .env.example                     # Example environment variables file
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── __init__.py
├── companies.json                   # List of companies to track
├── logging_config.py                # Logging configuration
└── run_pipeline.py                  # Main script to run the pipeline
```

## Getting Started

### Prerequisites

- Python 3.x
- Git
- Access to Google Custom Search API
- Access to OpenAI API

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Driisa/Business_reputation_tracker.git
   cd Business_reputation_tracker
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API keys and secrets:** Create a `.env` file in the root directory and add your API keys (refer to `.env.example`).

## Usage

To run the full pipeline locally:

```bash
python run_pipeline.py
```

## Future Improvements

- **Scalability**: Implement Kubernetes for auto-scaling agents.
- **Security**: Enhance credential management with solutions like HashiCorp Vault.
- **Data Sources**: Integrate additional third-party sources (e.g., Reddit, Twitter).
- **Robustness**: Add fallback mechanisms for LLM providers.
- **Compliance**: Expand adherence to international data governance frameworks (e.g., GDPR).
- **UI/UX**: Refine the dashboard with advanced analytics and customization options.

## License

This project is licensed under the MIT License.

## Contact

For inquiries, please contact the project participants.
