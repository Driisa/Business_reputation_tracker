"""
Synchronization module for keeping the frontend database in sync with the pipeline database.
Handles data transfer from object_store.db to to_frontend.db for frontend consumption.
"""

import sqlite3
import os
import time
import datetime

def create_frontend_db():
    """Create the frontend database with initial data from object_store.db"""
    
    # Connect to pipeline database
    conn_pipeline = sqlite3.connect('data/database/object_store.db')
    c_pipeline = conn_pipeline.cursor()
    
    # Create or recreate frontend database
    if os.path.exists('data/database/to_frontend.db'):
        os.remove('data/database/to_frontend.db')  # Remove existing file to start fresh
    conn_frontend = sqlite3.connect('data/database/to_frontend.db')
    c_frontend = conn_frontend.cursor()
    
    # Create the frontend table
    c_frontend.execute('''
    CREATE TABLE frontend_data (
        id INTEGER PRIMARY KEY,
        company_name TEXT,
        title TEXT,
        url TEXT,
        published_date TEXT,
        content_type TEXT,
        cleaned_text TEXT,
        sentiment_score REAL,
        sentiment_label TEXT,
        analysis_text TEXT,
        summary TEXT,
        last_updated TEXT
    )
    ''')
    
    # Initial data load from object_store.db to to_frontend.db
    c_pipeline.execute('''
    SELECT 
        sr.id,
        sr.company_name,
        sr.title,
        sr.link,
        sr.published_date,
        sr.content_type,
        cc.cleaned_text,
        ar.sentiment_score,
        ar.sentiment_label,
        ar.analysis_text,
        ar.summary
    FROM search_results sr
    LEFT JOIN scraped_content sc ON sr.id = sc.search_result_id
    LEFT JOIN cleaned_content cc ON sc.id = cc.scraped_content_id
    LEFT JOIN analysis_results ar ON cc.id = ar.cleaned_content_id
    ''')
    
    data = c_pipeline.fetchall()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Filter out rows with NULL values and add timestamp
    filtered_data = []
    for row in data:
        if None not in row:  # Check if any value in the row is NULL
            filtered_data.append(row + (current_time,))
    
    # Insert filtered data into frontend database
    if filtered_data:  # Only execute if there's data to insert
        c_frontend.executemany('''
        INSERT INTO frontend_data 
        (id, company_name, title, url, published_date, content_type, 
         cleaned_text, sentiment_score, sentiment_label, analysis_text, summary, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', filtered_data)
    
    # Commit changes and close connections
    conn_frontend.commit()
    conn_frontend.close()
    conn_pipeline.close()
    
    print("Frontend database created successfully with initial data.")

def sync_databases():
    """Synchronize data from object_store.db to to_frontend.db"""
    
    # Connect to both databases
    conn_pipeline = sqlite3.connect('data/database/object_store.db')
    conn_frontend = sqlite3.connect('data/database/to_frontend.db')
    
    # Create cursor objects
    c_pipeline = conn_pipeline.cursor()
    c_frontend = conn_frontend.cursor()
    
    # Get the latest data from pipeline
    c_pipeline.execute('''
    SELECT 
        sr.id,
        sr.company_name,
        sr.title,
        sr.link,
        sr.published_date,
        sr.content_type,
        cc.cleaned_text,
        ar.sentiment_score,
        ar.sentiment_label,
        ar.analysis_text,
        ar.summary
    FROM search_results sr
    LEFT JOIN scraped_content sc ON sr.id = sc.search_result_id
    LEFT JOIN cleaned_content cc ON sc.id = cc.scraped_content_id
    LEFT JOIN analysis_results ar ON cc.id = ar.cleaned_content_id
    ''')
    
    data = c_pipeline.fetchall()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # For each row, update or insert into frontend database
    for row in data:
        if None in row:  # Skip rows with NULL values
            continue
            
        id_val = row[0]
        
        # Check if the record exists
        c_frontend.execute("SELECT id FROM frontend_data WHERE id = ?", (id_val,))
        exists = c_frontend.fetchone()
        
        if exists:
            # Update existing record
            c_frontend.execute('''
            UPDATE frontend_data 
            SET 
                company_name = ?,
                title = ?,
                url = ?,
                published_date = ?,
                content_type = ?,
                cleaned_text = ?,
                sentiment_score = ?,
                sentiment_label = ?,
                analysis_text = ?,
                summary = ?,
                last_updated = ?
            WHERE id = ?
            ''', row[1:] + (current_time, id_val))
        else:
            # Insert new record
            c_frontend.execute('''
            INSERT INTO frontend_data 
            (id, company_name, title, url, published_date, content_type, 
             cleaned_text, sentiment_score, sentiment_label, analysis_text, summary, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', row + (current_time,))
    
    # Commit changes and close connections
    conn_frontend.commit()
    conn_pipeline.close()
    conn_frontend.close()
    
    print(f"Synchronization completed at {current_time}")

def scheduled_sync(interval_seconds=300):
    """Run a scheduled sync at regular intervals"""
    while True:
        sync_databases()
        print(f"Next sync in {interval_seconds} seconds")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    # Create the frontend database with initial data
    create_frontend_db()
    
    # Run one initial sync to ensure everything is up-to-date
    sync_databases()
    
    # Uncomment the following line to enable continuous syncing
    # scheduled_sync(interval_hours=24)  # Sync every 24 hours