# Business Reputation Tracker - UI Component

This is the web interface component of the Business Reputation Tracker application, providing a user-friendly dashboard for monitoring and analyzing company reputation data.

## Features

- User authentication system
- Interactive dashboard with real-time data visualization
- Sentiment analysis display
- Customizable filters for data analysis
- API key management interface

## Tech Stack

- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Database: SQLite
- Data Visualization: Plotly.js
- UI Framework: Custom CSS with responsive design

## Project Structure

```
UI/
├── static/          # Static assets (JS, CSS)
├── templates/       # HTML templates
│   ├── index.html   # Main dashboard
│   ├── login.html   # Authentication page
│   └── api_key.html # API key management
├── app.py           # Flask application
├── add_user_cli.py  # CLI tool for user management
└── requirements.txt # Python dependencies
```

## Installation

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   flask init-db
   ```

## Configuration

1. Set up environment variables:
   - `FLASK_APP=app.py`
   - `FLASK_ENV=development` (for development)

2. Configure the database path in `instance/config.py`

## Usage

1. Start the Flask development server:
   ```bash
   flask run
   ```

2. Access the application at `http://localhost:5000`

3. Log in with your credentials

## Adding Users

Use the CLI tool to add new users:
```bash
python add_user_cli.py --email user@example.com --password userpassword
```

## Development

- The application uses Flask's template system with Jinja2
- Static files are served from the `static` directory
- Database models are defined in the parent project's data module
- Logging is configured in `logging_config.py`

## Security

- Passwords are hashed using secure algorithms
- API keys are stored securely
- Session management is handled by Flask-Session
- CSRF protection is enabled

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details