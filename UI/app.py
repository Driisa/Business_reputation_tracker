from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta, datetime

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, 'app.log')
file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(pathname)s:%(lineno)d - %(message)s',
    '%Y-%m-%d %H:%M:%S'
))

# Get the Flask logger and configure it
logger = logging.getLogger('werkzeug')
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

# Configure the application logger
app_logger = logging.getLogger('app')
app_logger.addHandler(file_handler)
app_logger.setLevel(logging.INFO)

app = Flask(__name__)
app.secret_key = 'a_fixed_secret_key_for_sessions'  # Required for flash messages and sessions

# Configure session cookie settings
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME']= timedelta(days=1)
app.config['SESSION_USE_SIGNER'] = True  # Sign the session cookie for added security
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Enable session refresh on each request
app_logger.info(f"Session lifetime set to {app.config['PERMANENT_SESSION_LIFETIME']}")
app_logger.info(f"Session cookie settings: SECURE={app.config['SESSION_COOKIE_SECURE']}, HTTPONLY={app.config['SESSION_COOKIE_HTTPONLY']}, SAMESITE={app.config['SESSION_COOKIE_SAMESITE']}")
app_logger.info(f"Session refresh each request: {app.config['SESSION_REFRESH_EACH_REQUEST']}")

# Get the absolute path to the instance directory
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')

# Configure SQLAlchemy with multiple databases
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "database.db")}'

# Add frontend database bind
frontend_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'database', 'to_frontend.db')
app.config['SQLALCHEMY_BINDS'] = {
    'frontend': f'sqlite:///{frontend_db_path}'
}

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define User model
class CompanyMention(db.Model):
    __bind_key__ = 'frontend'
    __tablename__ = 'frontend_data'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200))
    url = db.Column(db.String(500))
    published_date = db.Column(db.String(200))
    content_type = db.Column(db.String(50))
    cleaned_text = db.Column(db.Text)
    sentiment_score = db.Column(db.Float)
    sentiment_label = db.Column(db.String(20))
    analysis_text = db.Column(db.Text)
    summary = db.Column(db.String(700))
    last_updated = db.Column(db.String(200))

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    
    def __init__(self, name, email, password, company_name):
        self.name = name
        self.email = email
        self.password = password
        self.company_name = company_name




@app.route('/add_user', methods=['POST'])
def add_user():
    app_logger.info("ADD_USER: Function called")
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    company_name = request.form.get('company_name')
    password = request.form.get('password')
    app_logger.info(f"ADD_USER: Form data: name={name}, email={email}, company_name={company_name}")
    
    # Validate data
    if not name or not email or not password or not company_name:
        app_logger.warning("ADD_USER: Validation failed: Missing required fields")
        flash('Name, email, company name, and password are required fields', 'error')
        return redirect(url_for('index'))
    
    try:
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            app_logger.warning("ADD_USER: Validation failed: Email already exists")
            flash('Email already exists', 'error')
            return redirect(url_for('index'))
            
        # Hash the password for security
        hashed_password = generate_password_hash(password)
        app_logger.info("ADD_USER: Password hashed successfully")
        
        # Create new user object
        new_user = User(name, email, hashed_password, company_name)
        
        # Add user to the database
        db.session.add(new_user)
        db.session.commit()
        app_logger.info(f"ADD_USER: User added successfully with ID: {new_user.id}")
        
        flash('User added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        app_logger.error(f"ADD_USER: Error adding user: {str(e)}")
        app_logger.error(f"ADD_USER: Error type: {type(e).__name__}")
        app_logger.error(f"ADD_USER: Error details: {str(e)}")
        flash(f'Error adding user: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    app_logger.info("LOGIN: Function called")
    app_logger.info(f"LOGIN: Request method: {request.method}")
    app_logger.info(f"LOGIN: Session before login: {session}")
    app_logger.info(f"LOGIN: Session type: {type(session).__name__}")
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        app_logger.info(f"LOGIN: Login attempt for email: {email}")
        
        # Validate input
        if not email or not password:
            app_logger.warning("LOGIN: Validation failed: Missing email or password")
            flash('Email and password are required', 'error')
            return redirect(url_for('login'))
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        app_logger.info(f"LOGIN: User found: {user is not None}")
        
        # Check if user exists and verify password
        if user and check_password_hash(user.password, password):
            # Login successful
            app_logger.info(f"LOGIN: Password verification successful for user ID: {user.id}")
            app_logger.info(f"LOGIN: Session before modification: {session}")
            
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['company_name'] = user.company_name  # Add company name to session
            # Force the session to be saved before redirecting
            session.modified = True
            
            app_logger.info(f"LOGIN: Session after modification: {session}")
            app_logger.info(f"LOGIN: Session permanent: {session.permanent}")
            app_logger.info(f"LOGIN: Session modified flag: {session.modified}")
            app_logger.info(f"LOGIN: Session data set: user_id={user.id}, user_name={user.name}, company_name={user.company_name}")
            app_logger.info(f"LOGIN: Session object details: {dir(session)}")
            
            flash('Login successful!', 'success')
            app_logger.info("LOGIN: Redirecting to index page")
            return redirect(url_for('index'))
        
        # Invalid credentials
        else:
            app_logger.warning("LOGIN: Authentication failed: Incorrect email or password")
            flash('Incorrect email or password', 'error')
            
    
    app_logger.info("LOGIN: Rendering login page")
    return render_template('login.html')

@app.route('/logout')
def logout():
    app_logger.info("LOGOUT: Function called")
    app_logger.info(f"LOGOUT: Current session data before logout: {session}")
    app_logger.info(f"LOGOUT: Session type: {type(session).__name__}")
    
    # Clear session
    session.pop('user_id', None)
    session.pop('user_name', None)
    app_logger.info("LOGOUT: Session data cleared")
    app_logger.info(f"LOGOUT: Session after clearing: {session}")
    
    flash('You have been logged out', 'success')
    app_logger.info("LOGOUT: Redirecting to login page")
    return redirect(url_for('login'))

@app.route('/')
def index():
    app_logger.info("INDEX: Function called")
    app_logger.info(f"INDEX: Session data: {session}")
    # Check if user is logged in
    if 'user_id' not in session:
        app_logger.info("INDEX: User not logged in, redirecting to login page")
        return redirect(url_for('login'))
    
    # Get current user data
    current_user = db.session.get(User, session['user_id'])
    if not current_user:
        app_logger.error('INDEX: User not found in database')
        return redirect(url_for('logout'))
    
    # Ensure company_name is in session
    if 'company_name' not in session:
        session['company_name'] = current_user.company_name
        session.modified = True
        app_logger.info(f"INDEX: Added company_name to session: {session['company_name']}")
    
    # Get company-specific mentions from frontend database
    company_mentions = CompanyMention.query.filter_by(company_name=current_user.company_name).all()
    for record in company_mentions:
        if isinstance(record.published_date, str):
            try:
                record.published_date = datetime.strptime(record.published_date, "%Y-%m-%d")
            except ValueError:
                # fallback if the string format is different or invalid
                print(f"Failed to parse date for record {record.id}: {record.published_date}")   
    
    return render_template('index.html', user=current_user, company_mentions=company_mentions)

if __name__ == '__main__':
    app_logger.info(f"URL Map: {app.url_map}")

    app.run(debug=True, use_reloader=False, threaded=True, processes=1, host='127.0.0.1')