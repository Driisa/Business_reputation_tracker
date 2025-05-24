import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
import traceback  # For detailed error tracing

# Application theme colors
COLORS = {
    'primary': '#2c3e50',
    'secondary': '#3498db',
    'accent': '#e74c3c',
    'light': '#ecf0f1',
    'dark': '#34495e',
    'background': '#f9f9f9',
    'positive': 'rgba(46, 204, 113, 0.7)',
    'neutral': 'rgba(241, 196, 15, 0.7)',
    'negative': 'rgba(231, 76, 60, 0.7)'
}

# Function to load data from the SQLite database
def load_data():
    try:
        print("\n" + "="*50)
        print("Attempting to connect to database...")
        
        # Try multiple possible paths to find the database
        possible_paths = [
            'to_frontend.db',  # Direct in current folder
            os.path.join('data', 'database', 'to_frontend.db'),  # Relative to current directory
            os.path.join('..', 'data', 'database', 'to_frontend.db'),  # Up one level then into data
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'database', 'to_frontend.db'),  # Up two levels
            os.path.join(os.path.dirname(__file__), 'data', 'database', 'to_frontend.db')  # From current file path
        ]
        
        print("Current working directory:", os.getcwd())
        print("__file__ location:", __file__)
        print("Looking for database in these locations:")
        for path in possible_paths:
            print(f"- {path} {'(EXISTS)' if os.path.exists(path) else '(NOT FOUND)'}")
        
        conn = None
        db_path = None
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"Found database at: {path}")
                db_path = path
                try:
                    conn = sqlite3.connect(path)
                    print(f"Successfully connected to database at {path}")
                    break
                except sqlite3.Error as e:
                    print(f"Could not connect to database at {path}: {e}")
        
        if conn is None:
            print("Database not found at any of the expected paths!")
            return pd.DataFrame()
        
        # Check if the table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables in database: {[table[0] for table in tables]}")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='frontend_data'")
        if not cursor.fetchone():
            print("Error: frontend_data table does not exist!")
            return pd.DataFrame()
        
        # Show table structure
        cursor.execute("PRAGMA table_info(frontend_data)")
        columns = cursor.fetchall()
        print(f"Columns in frontend_data:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Check if data exists
        cursor.execute("SELECT COUNT(*) FROM frontend_data")
        count = cursor.fetchone()[0]
        print(f"Found {count} rows in frontend_data table")
        
        if count == 0:
            print("Warning: frontend_data table is empty!")
            return pd.DataFrame()
        
        # Preview some data
        cursor.execute("SELECT * FROM frontend_data LIMIT 3")
        sample_rows = cursor.fetchall()
        print("Sample data (first 3 rows):")
        for row in sample_rows:
            print(f"  - {row}")
        
        # Get the data
        print("Executing SQL query: SELECT * FROM frontend_data")
        df = pd.read_sql_query("SELECT * FROM frontend_data", conn)
        print(f"Loaded {len(df)} rows of data with columns: {df.columns.tolist()}")
        conn.close()
        
        # Convert date columns to datetime
        for date_col in ['published_date', 'last_updated']:
            if date_col in df.columns:
                print(f"Converting {date_col} to datetime")
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                print(f"Sample of {date_col} after conversion: {df[date_col].head()}")
        
        # If sentiment_label is missing but sentiment_score exists, create it
        if 'sentiment_score' in df.columns and 'sentiment_label' not in df.columns:
            print("Creating sentiment_label from sentiment_score")
            df['sentiment_label'] = df['sentiment_score'].apply(
                lambda x: 'positive' if x > 0.66 else ('negative' if x < 0.33 else 'neutral')
            )
        
        print("=" * 50 + "\n")
        return df
    
    except Exception as e:
        print(f"Error loading data: {e}")
        print("Full traceback:")
        print(traceback.format_exc())
        return pd.DataFrame()

# Initialize Dash application
app = dash.Dash(
    __name__, 
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ],
    external_stylesheets=[
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css'
    ]
)
app.title = "Business Reputation Tracker"

# Define CSS styles
styles = {
    'container': {
        'max-width': '1200px',
        'margin': '0 auto',
        'padding': '20px',
        'fontFamily': 'Arial, sans-serif',
    },
    'header': {
        'textAlign': 'center',
        'padding': '20px',
        'backgroundColor': 'white',
        'borderRadius': '8px',
        'boxShadow': '0 2px 10px rgba(0,0,0,0.05)',
        'marginBottom': '20px'
    },
    'section': {
        'backgroundColor': 'white',
        'padding': '20px',
        'borderRadius': '8px',
        'boxShadow': '0 2px 10px rgba(0,0,0,0.05)',
        'marginBottom': '20px'
    },
    'flex': {
        'display': 'flex',
        'gap': '20px',
        'flexWrap': 'wrap'
    },
    'filter': {
        'flex': '1',
        'minWidth': '300px'
    },
    'chart': {
        'flex': '2',
        'minWidth': '500px'
    },
    'title': {
        'borderBottom': '2px solid #e0e6ed',
        'paddingBottom': '10px',
        'marginTop': '0',
        'marginBottom': '20px',
        'color': COLORS['primary']
    }
}

# Define the layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Company Mentions Dashboard", style={'color': COLORS['primary']}),
        html.P("Track and analyze company mentions and sentiment across various sources")
    ], style=styles['header']),
    
    # Filters and Stats
    html.Div([
        # Filters
        html.Div([
            html.H3("Filters", style=styles['title']),
            
            # Companies
            html.Div([
                html.Label("Select Companies:"),
                dcc.Dropdown(
                    id='company-filter',
                    multi=True,
                    placeholder="Select companies..."
                ),
            ], style={'marginBottom': '15px'}),
            
            # Date Range
            html.Div([
                html.Label("Date Range:"),
                dcc.DatePickerRange(
                    id='date-range',
                    start_date_placeholder_text="Start Date",
                    end_date_placeholder_text="End Date",
                    display_format='DD/MM/YYYY'
                ),
            ], style={'marginBottom': '15px'}),
            
            # Content Type
            html.Div([
                html.Label("Content Type:"),
                dcc.Dropdown(
                    id='content-type-filter',
                    multi=True,
                    placeholder="Select content types..."
                ),
            ], style={'marginBottom': '15px'}),
            
            # Apply Button
            html.Button(
                'Apply Filters', 
                id='apply-filters', 
                style={
                    'width': '100%',
                    'backgroundColor': COLORS['secondary'],
                    'color': 'white',
                    'padding': '10px',
                    'border': 'none',
                    'borderRadius': '5px',
                    'cursor': 'pointer'
                }
            ),
        ], style={**styles['section'], **styles['filter']}),
        
        # Stats
        html.Div([
            html.H3("Overview", style=styles['title']),
            
            # Stats row
            html.Div([
                # Total Mentions
                html.Div([
                    html.H4("Total Mentions", style={'textAlign': 'center', 'margin': '0', 'fontSize': '14px'}),
                    html.P(id="total-mentions", style={'textAlign': 'center', 'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0'})
                ], style={'flex': '1', 'backgroundColor': '#f8f9fa', 'padding': '15px', 'borderRadius': '5px'}),
                
                # Average Sentiment
                html.Div([
                    html.H4("Avg Sentiment", style={'textAlign': 'center', 'margin': '0', 'fontSize': '14px'}),
                    html.P(id="avg-sentiment", style={'textAlign': 'center', 'fontSize': '24px', 'fontWeight': 'bold', 'margin': '5px 0'})
                ], style={'flex': '1', 'backgroundColor': '#f8f9fa', 'padding': '15px', 'borderRadius': '5px', 'marginLeft': '10px'}),
            ], style={'display': 'flex', 'marginBottom': '20px'}),
            
            # Content type pie chart
            html.Div([
                html.H4("Mentions by Content Type"),
                dcc.Graph(id="content-type-chart")
            ])
        ], style={**styles['section'], **styles['chart']}),
    ], style={**styles['flex']}),
    
    # Sentiment Over Time Chart
    html.Div([
        html.H3("Sentiment Trends", style=styles['title']),
        dcc.Graph(id="sentiment-time-graph")
    ], style=styles['section']),
    
    # Company Comparison Chart
    html.Div([
        html.H3("Company Comparison", style=styles['title']),
        dcc.Graph(id="company-comparison-graph")
    ], style=styles['section']),
    
    # Mentions Table
    html.Div([
        html.H3("Detailed Mentions", style=styles['title']),
        dash_table.DataTable(
            id='mentions-table',
            page_size=10,
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '10px',
                'whiteSpace': 'normal',
                'height': 'auto',
            },
            style_header={
                'backgroundColor': COLORS['primary'],
                'color': 'white',
                'fontWeight': 'bold',
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': COLORS['light']
                },
                {
                    'if': {
                        'filter_query': '{sentiment_label} = "positive"',
                    },
                    'backgroundColor': COLORS['positive'],
                },
                {
                    'if': {
                        'filter_query': '{sentiment_label} = "negative"',
                    },
                    'backgroundColor': COLORS['negative'],
                }
            ],
        )
    ], style=styles['section']),
    
    # Footer
    html.Div([
        html.P("Business Reputation Tracker © 2025", style={'textAlign': 'center', 'color': COLORS['dark']})
    ]),
    
    # Hidden div for storing data - updated to have separate stores for initial and filtered data
    dcc.Store(id='initial-data'),  # Store for initial unfiltered data
    dcc.Store(id='filtered-data'),  # Store for data after filtering
    # Trigger for initial data load
    html.Div(id='load-trigger', style={'display': 'none'})
    
], style=styles['container'])

# Callback to load initial data
@app.callback(
    [Output('company-filter', 'options'),
     Output('company-filter', 'value'),
     Output('content-type-filter', 'options'),
     Output('content-type-filter', 'value'),
     Output('date-range', 'min_date_allowed'),
     Output('date-range', 'max_date_allowed'),
     Output('date-range', 'start_date'),
     Output('date-range', 'end_date'),
     Output('initial-data', 'data')],  # Changed to store in initial-data
    [Input('load-trigger', 'children')]
)
def initialize_data(_):
    print("Initializing data...")
    df = load_data()
    
    if df.empty:
        print("No data loaded")
        default_start = datetime.now() - timedelta(days=30)
        default_end = datetime.now()
        return [], [], [], [], default_start, default_end, default_start, default_end, []
    
    # Company filter options
    companies = sorted(df['company_name'].unique()) if 'company_name' in df.columns else []
    company_options = [{'label': company, 'value': company} for company in companies]
    
    # Content type filter options
    content_types = sorted(df['content_type'].unique()) if 'content_type' in df.columns else []
    content_type_options = [{'label': ct, 'value': ct} for ct in content_types]
    
    # Date range
    min_date = df['published_date'].min() if 'published_date' in df.columns and not df.empty else datetime.now() - timedelta(days=30)
    max_date = df['published_date'].max() if 'published_date' in df.columns and not df.empty else datetime.now()
    
    # Default to last 30 days
    end_date = max_date.date() if not pd.isna(max_date) else datetime.now().date()
    start_date = (end_date - timedelta(days=30)) if not pd.isna(end_date) else (datetime.now() - timedelta(days=30)).date()
    
    print(f"Initialization complete: {len(companies)} companies, {len(content_types)} content types")
    return (
        company_options,
        companies,  # Select all companies by default
        content_type_options,
        content_types,  # Select all content types by default
        min_date.date() if not pd.isna(min_date) else (datetime.now() - timedelta(days=30)).date(),
        max_date.date() if not pd.isna(max_date) else datetime.now().date(),
        start_date,
        end_date,
        df.to_dict('records')
    )

# New callback to copy initial data to filtered data on startup
@app.callback(
    Output('filtered-data', 'data'),
    [Input('initial-data', 'data')]
)
def initialize_filtered_data(initial_data):
    print(f"Initializing filtered data with {len(initial_data) if initial_data else 0} records")
    return initial_data

# Callback to apply filters
@app.callback(
    Output('filtered-data', 'data', allow_duplicate=True),  # Added allow_duplicate
    [Input('apply-filters', 'n_clicks')],
    [State('company-filter', 'value'),
     State('date-range', 'start_date'),
     State('date-range', 'end_date'),
     State('content-type-filter', 'value'),
     State('initial-data', 'data')],  # Added initial-data as a state
    prevent_initial_call=True  # Prevent this from running on page load
)
def filter_data(n_clicks, companies, start_date, end_date, content_types, initial_data):
    if n_clicks is None or not initial_data:
        return dash.no_update
    
    # Use initial data from store instead of reloading
    df = pd.DataFrame(initial_data)
    print(f"Filtering {len(df)} records based on user selections")
    
    if df.empty:
        return []
    
    # Apply filters
    filtered_df = df.copy()
    
    if companies and len(companies) > 0:
        filtered_df = filtered_df[filtered_df['company_name'].isin(companies)]
        print(f"After company filter: {len(filtered_df)} records")
    
    if start_date and end_date:
        # Ensure published_date is datetime
        if 'published_date' in filtered_df.columns:
            if not pd.api.types.is_datetime64_dtype(filtered_df['published_date']):
                filtered_df['published_date'] = pd.to_datetime(filtered_df['published_date'])
                
            filtered_df = filtered_df[(filtered_df['published_date'].dt.date >= pd.to_datetime(start_date).date()) & 
                               (filtered_df['published_date'].dt.date <= pd.to_datetime(end_date).date())]
            print(f"After date filter: {len(filtered_df)} records")
    
    if content_types and len(content_types) > 0:
        filtered_df = filtered_df[filtered_df['content_type'].isin(content_types)]
        print(f"After content type filter: {len(filtered_df)} records")
    
    result = filtered_df.to_dict('records')
    print(f"Returning {len(result)} filtered records")
    return result

# Callback to update overview statistics
@app.callback(
    [Output('total-mentions', 'children'),
     Output('avg-sentiment', 'children')],
    [Input('filtered-data', 'data')]
)
def update_stats(filtered_data):
    if not filtered_data:
        return "0", "0.00"
    
    df = pd.DataFrame(filtered_data)
    
    if df.empty:
        return "0", "0.00"
    
    total_mentions = len(df)
    
    avg_sentiment = df['sentiment_score'].mean() if 'sentiment_score' in df.columns else 0
    avg_sentiment_formatted = f"{avg_sentiment:.2f}"
    
    return str(total_mentions), avg_sentiment_formatted

# Callback to update content type chart
@app.callback(
    Output('content-type-chart', 'figure'),
    [Input('filtered-data', 'data')]
)
def update_content_type_chart(filtered_data):
    if not filtered_data:
        # Create an empty figure with a message
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                {
                    "text": "No data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#7f8c8d"}
                }
            ],
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    df = pd.DataFrame(filtered_data)
    
    if df.empty or 'content_type' not in df.columns:
        # Empty figure with message
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                {
                    "text": "No content type data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#7f8c8d"}
                }
            ],
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    # Count mentions by content type
    content_counts = df['content_type'].value_counts().reset_index()
    content_counts.columns = ['content_type', 'count']
    
    fig = px.pie(
        content_counts, 
        values='count', 
        names='content_type',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_layout(
        margin=dict(t=30, b=10, l=10, r=10),
        legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    fig.update_traces(
        textinfo='percent+label',
        textposition='inside',
        marker=dict(line=dict(color='white', width=2))
    )
    
    return fig

# Callback to update sentiment over time graph
@app.callback(
    Output('sentiment-time-graph', 'figure'),
    [Input('filtered-data', 'data')]
)
def update_sentiment_time_graph(filtered_data):
    if not filtered_data:
        # Create an empty figure with a message
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                {
                    "text": "No data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#7f8c8d"}
                }
            ],
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    df = pd.DataFrame(filtered_data)
    
    if df.empty or 'published_date' not in df.columns:
        # Empty figure with message
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                {
                    "text": "No time-based data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#7f8c8d"}
                }
            ],
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    # Ensure dates are in datetime format
    df['published_date'] = pd.to_datetime(df['published_date'])
    
    # Group by date and company, calculate average sentiment
    df['date'] = df['published_date'].dt.date
    sentiment_time = df.groupby(['date', 'company_name'])['sentiment_score'].mean().reset_index()
    
    # Create line chart
    fig = px.line(
        sentiment_time, 
        x='date', 
        y='sentiment_score', 
        color='company_name',
        title='Sentiment Trends Over Time',
        labels={'sentiment_score': 'Sentiment Score', 'date': 'Date', 'company_name': 'Company'},
        markers=True
    )
    
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Sentiment Score",
        legend_title="Company",
        hovermode="x unified",
        plot_bgcolor='rgba(240,240,240,0.3)',
        paper_bgcolor='white'
    )
    
    return fig

# Callback to update company comparison graph
@app.callback(
    Output('company-comparison-graph', 'figure'),
    [Input('filtered-data', 'data')]
)
def update_company_comparison(filtered_data):
    if not filtered_data:
        # Create an empty figure with a message
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                {
                    "text": "No data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#7f8c8d"}
                }
            ],
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    df = pd.DataFrame(filtered_data)
    
    if df.empty:
        # Empty figure with message
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                {
                    "text": "No company data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "#7f8c8d"}
                }
            ],
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig
    
    # Aggregate statistics by company
    company_stats = df.groupby('company_name').agg({
        'id': 'count', 
        'sentiment_score': 'mean'
    }).reset_index()
    
    company_stats.columns = ['company_name', 'mention_count', 'avg_sentiment']
    
    # Create a bubble chart
    fig = px.scatter(
        company_stats,
        x='mention_count',
        y='avg_sentiment',
        size='mention_count',
        color='company_name',
        text='company_name',
        size_max=50,
        title="Company Comparison: Mentions vs Sentiment",
        labels={
            'mention_count': 'Number of Mentions',
            'avg_sentiment': 'Average Sentiment Score',
            'company_name': 'Company'
        }
    )
    
    fig.update_traces(
        textposition='top center',
        marker=dict(
            opacity=0.8,
            line=dict(width=2, color='white'),
            sizemode='area'
        ),
        hovertemplate='<b>%{text}</b><br>Mentions: %{x}<br>Avg Sentiment: %{y:.2f}<extra></extra>'
    )
    
    fig.update_layout(
        xaxis_title="Number of Mentions",
        yaxis_title="Average Sentiment Score",
        legend_title="Company",
        hovermode="closest",
        plot_bgcolor='rgba(240,240,240,0.3)',
        paper_bgcolor='white'
    )
    
    return fig

# Callback to update mentions table
@app.callback(
    [Output('mentions-table', 'data'),
     Output('mentions-table', 'columns')],
    [Input('filtered-data', 'data')]
)
def update_mentions_table(filtered_data):
    if not filtered_data:
        return [], []
    
    df = pd.DataFrame(filtered_data)
    
    if df.empty:
        return [], []
    
    # Select columns for the table
    table_columns = ['company_name', 'title', 'published_date', 'content_type', 
                    'sentiment_score', 'sentiment_label', 'url']
    
    # Ensure all columns exist in the dataframe
    existing_columns = [col for col in table_columns if col in df.columns]
    table_df = df[existing_columns].copy()
    
    # Format dates
    if 'published_date' in table_df.columns:
        table_df['published_date'] = pd.to_datetime(table_df['published_date']).dt.strftime('%Y-%m-%d')
    
    # Format sentiment score
    if 'sentiment_score' in table_df.columns:
        table_df['sentiment_score'] = table_df['sentiment_score'].round(2)
    
    # Define columns with better formatting
    columns = [
        {'name': 'Company', 'id': 'company_name'},
        {'name': 'Title', 'id': 'title'},
        {'name': 'Date', 'id': 'published_date'},
        {'name': 'Content Type', 'id': 'content_type'},
        {'name': 'Sentiment Score', 'id': 'sentiment_score'},
        {'name': 'Sentiment', 'id': 'sentiment_label'},
        {'name': 'Source URL', 'id': 'url', 'presentation': 'markdown'}
    ]
    
    # Keep only columns that exist in the dataframe
    columns = [col for col in columns if col['id'] in existing_columns]
    
    return table_df.to_dict('records'), columns

# Run the app
if __name__ == '__main__':
    print("\n" + "="*50)
    print("Starting the Dash application...")
    print("Current working directory:", os.getcwd())
    print("=" * 50 + "\n")
    
    # Try to create a simple SQLite database with test data if no database exists
    try:
        # Check if any of our potential database paths exists
        db_paths = [
            'to_frontend.db',
            os.path.join('data', 'database', 'to_frontend.db'),
            os.path.join('..', 'data', 'database', 'to_frontend.db')
        ]
        
        db_exists = any(os.path.exists(path) for path in db_paths)
        
        if not db_exists:
            print("No database found. Creating a sample database 'to_frontend.db' in the current directory...")
            
            # Create a sample database with test data in the current directory
            conn = sqlite3.connect('to_frontend.db')
            cursor = conn.cursor()
            
            # Create frontend_data table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS frontend_data (
                id INTEGER PRIMARY KEY,
                company_name TEXT,
                title TEXT,
                content TEXT,
                content_type TEXT,
                published_date TEXT,
                last_updated TEXT,
                sentiment_score REAL,
                sentiment_label TEXT,
                url TEXT
            )
            ''')
            
            # Sample companies
            companies = ['TechCorp', 'EcoSolutions', 'FinanceGroup', 'HealthPlus']
            
            # Sample content types
            content_types = ['News Article', 'Blog Post', 'Social Media', 'Press Release']
            
            # Sample data
            sample_data = []
            
            # Generate 50 random entries
            import random
            from datetime import datetime, timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            
            for i in range(1, 51):
                company = random.choice(companies)
                content_type = random.choice(content_types)
                
                # Random date in the last 60 days
                days_ago = random.randint(0, 60)
                pub_date = (end_date - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                update_date = (end_date - timedelta(days=days_ago-1)).strftime('%Y-%m-%d')
                
                # Random sentiment
                sentiment_score = round(random.uniform(0, 1), 2)
                sentiment_label = 'positive' if sentiment_score > 0.66 else ('negative' if sentiment_score < 0.33 else 'neutral')
                
                sample_data.append((
                    i,
                    company,
                    f"{company} {content_type} #{i}",
                    f"This is sample content for {company}.",
                    content_type,
                    pub_date,
                    update_date,
                    sentiment_score,
                    sentiment_label,
                    f"https://example.com/{company.lower()}/{i}"
                ))
            
            # Insert sample data
            cursor.executemany('''
            INSERT INTO frontend_data (id, company_name, title, content, content_type, 
                                     published_date, last_updated, sentiment_score, 
                                     sentiment_label, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_data)
            
            conn.commit()
            conn.close()
            
            print("Sample database created successfully with 50 entries!")
    except Exception as e:
        print(f"Error creating sample database: {e}")
    
    app.run_server(debug=True, port=8050)