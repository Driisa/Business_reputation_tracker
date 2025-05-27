from app import db, User, app
from werkzeug.security import generate_password_hash

def get_valid_input(prompt, validator=None, allow_empty=False):
    while True:
        value = input(prompt).strip()
        if not value and not allow_empty:
            app_logger.warning("This field cannot be empty. Please try again.")
            continue
        if validator and value:
            try:
                value = validator(value)
                return value
            except ValueError as e:
                app_logger.warning(f"Invalid input: {e}")
                continue
        return value

def validate_email(email):
    if '@' not in email or '.' not in email:
        raise ValueError("Please enter a valid email address")
    return email

def add_user_interactive():
    app_logger.info("=== Add New User ===")
    
    try:
        # Get user input with validation
        name = get_valid_input("Enter name: ")
        email = get_valid_input("Enter email: ", validate_email)
        company_name = get_valid_input("Enter company name: ")
        
        # Get and confirm password
        while True:
            password = get_valid_input("Enter password: ")
            confirm_password = get_valid_input("Confirm password: ")
            
            if password != confirm_password:
                app_logger.warning("Passwords do not match. Please try again.")
                continue
            break

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Create new user
        with app.app_context():
            # Check if email already exists
            if User.query.filter_by(email=email).first():
                app_logger.error("Error: Email already exists!")
                return

            # Create and add new user
            new_user = User(name=name, email=email, password=hashed_password, company_name=company_name)
            db.session.add(new_user)
            db.session.commit()
            app_logger.info(f"Success! User {name} has been added with ID: {new_user.id}")

    except Exception as e:
        app_logger.error(f"Error: {str(e)}")
        if 'db' in locals():
            db.session.rollback()

if __name__ == '__main__':
    add_user_interactive()