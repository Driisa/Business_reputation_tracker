from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from backend.app.database import get_db_session, Company
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

@app.route('/')
def dashboard():
    session = get_db_session()
    companies = session.query(Company).all()
    session.close()
    return render_template('dashboard.html', companies=companies)

@app.route('/companies/add', methods=['GET', 'POST'])
def add_company():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        session = get_db_session()
        try:
            company = Company(name=name, description=description)
            session.add(company)
            session.commit()
            flash('Company added successfully!', 'success')
        except Exception as e:
            session.rollback()
            flash('Error adding company. Company name might already exist.', 'error')
        finally:
            session.close()
        return redirect(url_for('dashboard'))
    
    return render_template('add_company.html')

@app.route('/companies/<int:company_id>/edit', methods=['GET', 'POST'])
def edit_company(company_id):
    session = get_db_session()
    company = session.query(Company).get_or_404(company_id)
    
    if request.method == 'POST':
        company.name = request.form.get('name')
        company.description = request.form.get('description')
        try:
            session.commit()
            flash('Company updated successfully!', 'success')
        except Exception as e:
            session.rollback()
            flash('Error updating company.', 'error')
        finally:
            session.close()
        return redirect(url_for('dashboard'))
    
    session.close()
    return render_template('edit_company.html', company=company)

@app.route('/companies/<int:company_id>/delete', methods=['POST'])
def delete_company(company_id):
    session = get_db_session()
    company = session.query(Company).filter_by(id=company_id).first()
    
    if company is None:
        flash('Company not found.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        session.delete(company)
        session.commit()
        flash('Company deleted successfully!', 'success')
    except Exception as e:
        session.rollback()
        flash('Error deleting company.', 'error')
    finally:
        session.close()
    return redirect(url_for('dashboard'))

@app.route('/api/companies', methods=['GET'])
def get_companies():
    session = get_db_session()
    companies = session.query(Company).all()
    session.close()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'description': c.description,
        'created_at': c.created_at.isoformat(),
        'updated_at': c.updated_at.isoformat()
    } for c in companies])

if __name__ == '__main__':
    app.run(debug=True) 