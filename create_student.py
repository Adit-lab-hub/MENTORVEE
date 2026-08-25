import sys
import os
import uuid
import re
import random
import string

# Add backend folder to path so we can import the app modules
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

try:
    from app.core.database import SessionLocal
    from app.models.models import User, ClassSubject
    from app.core.security import get_password_hash
    from app.core.config import settings
except ImportError as e:
    print(f"Error importing app modules: {e}")
    print("Please make sure you run this script from the project root and that the virtual environment is activated.")
    sys.exit(1)

def validate_password_strength(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    if not re.search("[_@$!%*#?&+-]", password):
        return False
    return True

def generate_strong_password() -> str:
    # Generate a strong password meeting the strength requirements
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "_@$!%*#?&+-"
    
    password = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digits),
        random.choice(special)
    ]
    
    all_chars = lower + upper + digits + special
    password += [random.choice(all_chars) for _ in range(8)]
    random.shuffle(password)
    return "".join(password)

def create_student(email: str, password: str, class_id: int):
    email = email.strip().lower()
    
    # Simple email validation
    if "@" not in email:
        print("Error: Invalid email format.")
        return False
        
    domain = email.split("@")[-1]
    if settings.ALLOWED_EMAIL_DOMAINS and domain not in settings.ALLOWED_EMAIL_DOMAINS:
        print(f"Error: Email domain must be one of: {settings.ALLOWED_EMAIL_DOMAINS}")
        return False

    if not validate_password_strength(password):
        print("Error: Password must be at least 8 characters long and contain uppercase, lowercase, numbers, and special characters.")
        return False

    db = SessionLocal()
    try:
        # Verify class exists
        cls = db.query(ClassSubject).filter(ClassSubject.id == class_id).first()
        if not cls:
            print(f"Error: Class with ID {class_id} does not exist.")
            return False

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"Error: A user with email '{email}' already exists.")
            return False

        # Create new student
        new_student = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=get_password_hash(password),
            role="student",
            status="active",
            class_id=class_id
        )
        db.add(new_student)
        db.commit()
        print(f"\n[SUCCESS] Student account created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Role: student")
        print(f"Status: active")
        print(f"Assigned Class: {cls.name} ({cls.code})")
        return True
    except Exception as e:
        db.rollback()
        print(f"Error creating student account: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    print("--- MENTORVEE Student Account Creator ---")
    
    db = SessionLocal()
    classes = db.query(ClassSubject).all()
    db.close()
    
    if not classes:
        print("Error: No classes found in the database. Please create a class first.")
        sys.exit(1)
        
    parser = argparse.ArgumentParser(description="Create a MENTORVEE Student Account")
    parser.add_argument("--email", type=str, help="Student email address")
    parser.add_argument("--password", type=str, help="Student password")
    parser.add_argument("--class-id", type=int, help="Class ID to enroll student in")
    
    args = parser.parse_args()
    
    if args.email or args.password or args.class_id:
        # Non-interactive mode
        email = args.email if args.email else f"student{random.randint(100, 999)}@collegename.edu"
        password = args.password if args.password else generate_strong_password()
        class_id = args.class_id if args.class_id else classes[0].id
        create_student(email, password, class_id)
    else:
        # Interactive mode
        default_email = f"student{random.randint(100, 999)}@collegename.edu"
        email_input = input(f"Enter student email address [default: {default_email}]: ").strip()
        email = email_input if email_input else default_email
        
        default_password = generate_strong_password()
        password_input = input(f"Enter password [default/generated: {default_password}]: ").strip()
        password = password_input if password_input else default_password
        
        print("\nAvailable Classes:")
        for cls in classes:
            print(f"  [{cls.id}] {cls.name} ({cls.code})")
            
        class_id_str = input(f"Select Class ID [default: {classes[0].id}]: ").strip()
        try:
            class_id = int(class_id_str) if class_id_str else classes[0].id
        except ValueError:
            class_id = classes[0].id
            
        create_student(email, password, class_id)

