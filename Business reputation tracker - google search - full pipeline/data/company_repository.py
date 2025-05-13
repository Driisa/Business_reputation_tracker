"""
Repository module for company-related database operations.
Handles CRUD operations for companies in the companies.db database.
"""

import sqlite3
from typing import List, Dict, Any

def get_db_connection():
    """Create a database connection."""
    return sqlite3.connect('data/database/companies.db')

def get_all_companies() -> List[Dict[str, Any]]:
    """Retrieve all companies from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM companies')
    companies = cursor.fetchall()
    
    # Convert to list of dictionaries
    columns = [description[0] for description in cursor.description]
    result = []
    for company in companies:
        company_dict = dict(zip(columns, company))
        # Convert services string back to list
        company_dict['services'] = company_dict['services'].split(',')
        result.append(company_dict)
    
    conn.close()
    return result

def get_company_by_id(company_id: str) -> Dict[str, Any]:
    """Retrieve a specific company by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM companies WHERE company_id = ?', (company_id,))
    company = cursor.fetchone()
    
    if company:
        columns = [description[0] for description in cursor.description]
        company_dict = dict(zip(columns, company))
        company_dict['services'] = company_dict['services'].split(',')
    else:
        company_dict = None
    
    conn.close()
    return company_dict

def add_company(company_data: Dict[str, Any]) -> bool:
    """Add a new company to the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Convert services list to comma-separated string
        services_str = ','.join(company_data['services'])
        
        cursor.execute('''
        INSERT INTO companies 
        (company_id, company_name, industry, location, description, services)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            company_data['company_id'],
            company_data['company_name'],
            company_data['industry'],
            company_data['location'],
            company_data['description'],
            services_str
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding company: {e}")
        return False

def update_company(company_id: str, company_data: Dict[str, Any]) -> bool:
    """Update an existing company in the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Convert services list to comma-separated string
        services_str = ','.join(company_data['services'])
        
        cursor.execute('''
        UPDATE companies 
        SET company_name = ?, industry = ?, location = ?, description = ?, services = ?
        WHERE company_id = ?
        ''', (
            company_data['company_name'],
            company_data['industry'],
            company_data['location'],
            company_data['description'],
            services_str,
            company_id
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating company: {e}")
        return False

def delete_company(company_id: str) -> bool:
    """Delete a company from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM companies WHERE company_id = ?', (company_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting company: {e}")
        return False 