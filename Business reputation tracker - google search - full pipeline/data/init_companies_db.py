"""
Setup module for the companies database.
Initializes the companies database schema and populates it with initial data from companies.json.
"""

import sqlite3
import json
import os

def setup_database():
    # Create database connection
    conn = sqlite3.connect('data/database/companies.db')
    cursor = conn.cursor()

    # Create companies table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS companies (
        company_id TEXT PRIMARY KEY,
        company_name TEXT NOT NULL,
        industry TEXT,
        location TEXT,
        description TEXT,
        services TEXT
    )
    ''')

    # Read the JSON file
    with open('companies.json', 'r') as f:
        companies = json.load(f)

    # Insert data from JSON into database
    for company in companies:
        # Convert services list to comma-separated string
        services_str = ','.join(company['services'])
        
        cursor.execute('''
        INSERT OR REPLACE INTO companies 
        (company_id, company_name, industry, location, description, services)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            company['company_id'],
            company['company_name'],
            company['industry'],
            company['location'],
            company['description'],
            services_str
        ))

    # Commit changes and close connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()
    print("Database setup completed successfully!") 