import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_tables():
    """Create necessary tables for the application"""
    conn = None
    try:
        # Connect to the PostgreSQL database
        conn = psycopg2.connect(
            host=os.getenv('PGHOST'),
            database=os.getenv('PGDATABASE'),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD'),
            port=os.getenv('PGPORT')
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Print connection info for debugging
        print(f"Connected to database: {os.getenv('PGDATABASE')} on host: {os.getenv('PGHOST')}")
        
        # Create users table if not exists
        cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(255) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            company VARCHAR(255),
            created_at TIMESTAMP NOT NULL,
            subscription_type VARCHAR(50) NOT NULL,
            last_login TIMESTAMP,
            password VARCHAR(255) NOT NULL
        );
        ''')
        
        # Create support_tickets table if not exists
        cur.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) REFERENCES users(id),
            email VARCHAR(255) NOT NULL,
            subject VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            created_at TIMESTAMP NOT NULL
        );
        ''')
        
        # Create reviews table if not exists
        cur.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) REFERENCES users(id),
            email VARCHAR(255) NOT NULL,
            rating INTEGER NOT NULL,
            review TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        );
        ''')
        
        # Create contract_reminders table if not exists
        cur.execute('''
        CREATE TABLE IF NOT EXISTS contract_reminders (
            id SERIAL PRIMARY KEY,
            user_email VARCHAR(255) NOT NULL,
            contract_name VARCHAR(255) NOT NULL,
            reminder_date DATE NOT NULL,
            description TEXT,
            status VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        
        # Create notification_settings table if not exists
        cur.execute('''
        CREATE TABLE IF NOT EXISTS notification_settings (
            user_email VARCHAR(255) PRIMARY KEY,
            email_enabled BOOLEAN DEFAULT TRUE,
            phone_number VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        
        # Commit the changes
        conn.commit()
        
        # Print success message
        print("Tables created successfully")
        
        # Close cursor
        cur.close()
    
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating tables: {error}")
    
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    create_tables()