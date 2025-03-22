import streamlit as st
import supabase
from dotenv import load_dotenv
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import uuid

# First Streamlit command - must be at the very top
st.set_page_config(
    page_title="Legal Contract Analysis System",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_client = None

# Try to connect to Supabase, but handle errors gracefully
try:
    supabase_client = supabase.create_client(supabase_url, supabase_key)
    print("Successfully connected to Supabase")
except Exception as e:
    print(f"Warning: Could not connect to Supabase: {str(e)}")
    print("Using local session storage instead")

# Email configuration
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Define usage limits for free tier
FREE_TIER_LIMITS = {
    'reports_per_day': 3,
    'queries_per_day': 10,
    'analysis_per_day': 5,
    'generation_per_day': 2
}

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'subscription_type' not in st.session_state:
        st.session_state.subscription_type = 'free'
    if 'usage_counts' not in st.session_state:
        st.session_state.usage_counts = {
            'reports': 0,
            'queries': 0,
            'analysis': 0,
            'last_reset': datetime.now().date()
        }
    if 'show_upgrade_popup' not in st.session_state:
        st.session_state.show_upgrade_popup = False
    if 'show_support' not in st.session_state:
        st.session_state.show_support = False
    if 'support_tab' not in st.session_state:
        st.session_state.support_tab = 'Submit Ticket'
    if 'selected_language' not in st.session_state:
        st.session_state.selected_language = 'en'
    if 'show_payment' not in st.session_state:
        st.session_state.show_payment = False
    if 'contract_text' not in st.session_state:
        st.session_state.contract_text = ""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'risks_opportunities' not in st.session_state:
        st.session_state.risks_opportunities = None
    if 'clause_analysis' not in st.session_state:
        st.session_state.clause_analysis = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"
    if 'email' not in st.session_state:
        st.session_state.email = ""

def reset_daily_counts():
    """Reset daily usage counts if it's a new day"""
    today = datetime.now().date()
    if (st.session_state.usage_counts['last_reset'] != today):
        st.session_state.usage_counts = {
            'reports': 0,
            'queries': 0,
            'analysis': 0,
            'last_reset': today
        }

def check_usage_limits(action_type):
    """Check if user has reached their usage limits"""
    if st.session_state.subscription_type == 'paid':
        return True
    
    reset_daily_counts()
    
    limits = {
        'reports': FREE_TIER_LIMITS['reports_per_day'],
        'queries': FREE_TIER_LIMITS['queries_per_day'],
        'analysis': FREE_TIER_LIMITS['analysis_per_day'],
        'generation': FREE_TIER_LIMITS['generation_per_day']
    }
    
    # Initialize the generation counter if it doesn't exist
    if 'generation' not in st.session_state.usage_counts:
        st.session_state.usage_counts['generation'] = 0
    
    if st.session_state.usage_counts[action_type] >= limits[action_type]:
        st.session_state.show_upgrade_popup = True
        return False
    
    st.session_state.usage_counts[action_type] += 1
    return True

def validate_email(email):
    """Validate email format"""
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    if not (has_upper and has_lower and has_digit):
        return False, "Password must contain uppercase, lowercase, and digits"
        
    return True, "Password is valid"

def register_user(email, password, name, company=None):
    """Register a new user"""
    try:
        # Create user data
        user_data = {
            'id': str(uuid.uuid4()),
            'email': email,
            'name': name,
            'company': company if company else "",
            'created_at': datetime.now().isoformat(),
            'subscription_type': 'free',
            'last_login': datetime.now().isoformat(),
            'password': password  # In production, you should hash this password
        }
        
        # If Supabase client is available, try to use it
        if supabase_client:
            # Check if user already exists
            try:
                response = supabase_client.table('users').select('*').eq('email', email).execute()
                if response.data and len(response.data) > 0:
                    return False, "Email already registered. Please login or use a different email."
                
                # Insert user into Supabase
                response = supabase_client.table('users').insert(user_data).execute()
                
                if not response.data:
                    print("Failed to create user in database, using session storage instead")
            except Exception as db_error:
                print(f"Database operation failed: {str(db_error)}")
                print("Using session storage as fallback")
        
        # Session storage fallback - always store in session state
        if 'users' not in st.session_state:
            st.session_state.users = {}
        
        # Check if email exists in session state
        if email in st.session_state.users and email != "demo@example.com":
            return False, "Email already registered. Please login or use a different email."
            
        # Store in session state
        st.session_state.users[email] = user_data
            
        # Set up session state
        st.session_state.authenticated = True
        st.session_state.user = type('obj', (object,), user_data)
        st.session_state.subscription_type = 'free'
        st.session_state.email = email
        
        # Try to send welcome email
        try:
            send_welcome_email(email, name)
        except Exception as mail_error:
            print(f"Failed to send welcome email: {str(mail_error)}")
        
        return True, "Registration successful!"
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return False, f"Registration error: {str(e)}"

def login_user(email, password):
    """Log in an existing user"""
    try:
        # Special case for demo account
        if email == "demo@example.com" and password == "Demo@123":
            user_data = {
                'id': str(uuid.uuid4()),
                'email': email,
                'name': "Demo User",
                'company': "Demo Company",
                'created_at': datetime.now().isoformat(),
                'subscription_type': 'free',
                'last_login': datetime.now().isoformat(),
                'password': password
            }
            
            # Set up session state
            st.session_state.authenticated = True
            st.session_state.user = type('obj', (object,), user_data)
            st.session_state.subscription_type = 'free'
            st.session_state.email = email
            
            # Store in session state for future logins
            if 'users' not in st.session_state:
                st.session_state.users = {}
            st.session_state.users[email] = user_data
            
            return True, "Login successful! Welcome to the demo account."
        
        # First check session state for faster login and offline functionality
        if 'users' in st.session_state and email in st.session_state.users:
            user = st.session_state.users[email]
            
            # Verify password (simple check for demo)
            if user['password'] != password:
                return False, "Invalid password. Please try again."
                
            # Set up session state
            st.session_state.authenticated = True
            st.session_state.user = type('obj', (object,), user)
            st.session_state.subscription_type = user.get('subscription_type', 'free')
            st.session_state.email = email
            
            # Update last login time in session
            user['last_login'] = datetime.now().isoformat()
            st.session_state.users[email] = user
            
            return True, "Login successful!"
        
        # If not in session state and Supabase is available, try that
        if supabase_client:
            try:
                # Check if user exists in Supabase
                response = supabase_client.table('users').select('*').eq('email', email).execute()
                
                if response.data and len(response.data) > 0:
                    user = response.data[0]
                    
                    # In a real application, you would use proper password hashing and verification
                    if user['password'] != password:
                        return False, "Invalid password. Please try again."
                    
                    # Set up session state
                    st.session_state.authenticated = True
                    st.session_state.user = type('obj', (object,), user)
                    st.session_state.subscription_type = user.get('subscription_type', 'free')
                    st.session_state.email = email
                    
                    # Store in session state for future logins
                    if 'users' not in st.session_state:
                        st.session_state.users = {}
                    st.session_state.users[email] = user
                    
                    # Try to update last login time in Supabase
                    try:
                        supabase_client.table('users').update({
                            'last_login': datetime.now().isoformat()
                        }).eq('id', user['id']).execute()
                    except Exception as update_error:
                        print(f"Could not update login time in database: {str(update_error)}")
                    
                    return True, "Login successful!"
            except Exception as db_error:
                print(f"Database login error: {str(db_error)}")
                # Continue to return user not found
        
        return False, "User not found. Please register or use the demo account (demo@example.com / Demo@123)"
    except Exception as e:
        print(f"Login error: {str(e)}")
        return False, f"Login error: {str(e)}"

def logout_user():
    """Log out the current user"""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.subscription_type = 'free'
    st.session_state.email = ""
    st.session_state.usage_counts = {
        'reports': 0,
        'queries': 0,
        'analysis': 0,
        'last_reset': datetime.now().date()
    }
    st.session_state.show_upgrade_popup = False
    st.rerun()

def send_welcome_email(email, name):
    """Send welcome email to new users"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = email
        msg['Subject'] = "Welcome to Legal Contract Analysis System"
        
        body = f"""
        <html>
        <body>
            <h2>Welcome to Legal Contract Analysis System, {name}!</h2>
            <p>Thank you for registering with our platform. We're excited to help you analyze and understand your legal contracts better.</p>
            <p>With our system, you can:</p>
            <ul>
                <li>Upload and analyze contracts in seconds</li>
                <li>Get detailed risk assessments</li>
                <li>Identify opportunities and potential issues</li>
                <li>Generate comprehensive reports</li>
            </ul>
            <p>Get started today by uploading your first contract!</p>
            <p>Best regards,<br>
            Legal Contract Analysis Team</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

def submit_support_ticket(subject, description, category):
    """Submit a support ticket"""
    try:
        ticket_id = str(uuid.uuid4())
        ticket_data = {
            'user_id': st.session_state.user.id,
            'email': st.session_state.user.email,
            'subject': subject,
            'description': description,
            'category': category,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'ticket_id': ticket_id
        }
        
        # Store in session state for local persistence
        if 'support_tickets' not in st.session_state:
            st.session_state.support_tickets = []
        
        st.session_state.support_tickets.append(ticket_data)
        
        # Try to store in Supabase if available
        if supabase_client:
            try:
                response = supabase_client.table('support_tickets').insert(ticket_data).execute()
                print("Ticket saved to database successfully")
            except Exception as db_error:
                print(f"Could not save ticket to database: {str(db_error)}")
                print("Ticket saved to session state only")
        
        return True, "Support ticket submitted successfully!"
    except Exception as e:
        print(f"Error submitting ticket: {str(e)}")
        return False, f"Error submitting ticket: {str(e)}"

def submit_review(rating, review_text):
    """Submit a product review"""
    try:
        review_data = {
            'user_id': st.session_state.user.id,
            'email': st.session_state.user.email,
            'rating': rating,
            'review': review_text,
            'created_at': datetime.now().isoformat(),
            'review_id': str(uuid.uuid4())
        }
        
        # Store in session state
        if 'reviews' not in st.session_state:
            st.session_state.reviews = []
        
        st.session_state.reviews.append(review_data)
        
        # Try to save to Supabase if available
        if supabase_client:
            try:
                response = supabase_client.table('reviews').insert(review_data).execute()
                print("Review saved to database successfully")
            except Exception as db_error:
                print(f"Could not save review to database: {str(db_error)}")
                print("Review saved to session state only")
        
        return True, "Review submitted successfully!"
    except Exception as e:
        print(f"Error submitting review: {str(e)}")
        return False, f"Error submitting review: {str(e)}"

def get_user_tickets():
    """Get support tickets for the current user"""
    tickets = []
    
    # First try to get tickets from session state
    if 'support_tickets' in st.session_state:
        user_id = st.session_state.user.id
        tickets = [ticket for ticket in st.session_state.support_tickets 
                  if ticket.get('user_id') == user_id]
    
    # If Supabase is available, try to get tickets from database
    if supabase_client:
        try:
            response = supabase_client.table('support_tickets')\
                .select('*')\
                .eq('user_id', st.session_state.user.id)\
                .execute()
            
            if response.data:
                # If we got tickets from both sources, merge them
                # (using ticket_id to avoid duplicates)
                session_ticket_ids = [t.get('ticket_id') for t in tickets]
                for db_ticket in response.data:
                    if db_ticket.get('ticket_id') not in session_ticket_ids:
                        tickets.append(db_ticket)
        except Exception as e:
            print(f"Error fetching tickets from database: {str(e)}")
            print("Using tickets from session state only")
    
    return tickets

def show_support_interface():
    """Display the support interface"""
    st.sidebar.write("---")
    if st.sidebar.button("📞 Customer Support"):
        st.session_state.show_support = not st.session_state.show_support

    if st.session_state.show_support:
        st.title("Customer Support Center")
        
        tabs = ["Submit Ticket", "My Tickets", "Rate & Review"]
        selected_tab = st.radio("Select Option", tabs, key="support_tab")
        
        if selected_tab == "Submit Ticket":
            st.header("Submit Support Ticket")
            
            subject = st.text_input("Subject")
            category = st.selectbox("Category", 
                ["Technical Issue", "Billing Question", "Feature Request", "General Inquiry"])
            description = st.text_area("Description", height=150)
            
            if st.button("Submit Ticket"):
                if subject and description:
                    success, message = submit_support_ticket(subject, description, category)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill in all fields")
        
        elif selected_tab == "My Tickets":
            st.header("My Support Tickets")
            
            tickets = get_user_tickets()
            
            if not tickets:
                st.info("You haven't submitted any support tickets yet.")
            else:
                for ticket in tickets:
                    with st.expander(f"{ticket['subject']} ({ticket['status'].title()})"):
                        st.write(f"**Category:** {ticket['category']}")
                        st.write(f"**Date:** {ticket['created_at'].split('T')[0]}")
                        st.write(f"**Description:**")
                        st.write(ticket['description'])
                        
                        if ticket['status'] == 'open':
                            st.info("This ticket is still open. Our support team will respond shortly.")
                        elif ticket['status'] == 'in_progress':
                            st.warning("This ticket is being processed by our support team.")
                        elif ticket['status'] == 'resolved':
                            st.success("This ticket has been resolved.")
        
        elif selected_tab == "Rate & Review":
            st.header("Rate Our Service")
            
            rating = st.slider("How would you rate our service?", 1, 5, 5)
            review_text = st.text_area("Your Review", height=150)
            
            if st.button("Submit Review"):
                if review_text:
                    success, message = submit_review(rating, review_text)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.warning("Please enter your review")

def show_login_form(mode="login"):
    """Display login or registration form"""
    if mode == "login":
        st.title("Login")
        
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if email and password:
                    success, message = login_user(email, password)
                    if success:
                        st.success(message)
                        # Redirect to home page after successful login
                        st.session_state.current_page = "Home"
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please enter your email and password")
                    
        st.markdown("Don't have an account? [Register here](#)")
        if st.button("Register Instead"):
            st.session_state.current_page = "Register"
            st.rerun()
            
        # Demo account option
        st.markdown("---")
        st.markdown("### Try with a Demo Account")
        if st.button("Use Demo Account"):
            success, message = login_user("demo@example.com", "Demo@123")
            if success:
                st.success(message)
                st.session_state.current_page = "Home"
                st.rerun()
            else:
                st.error(message)
    
    elif mode == "register":
        st.title("Register")
        
        with st.form("register_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Email")
            company = st.text_input("Company (Optional)")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if name and email and password and confirm_password:
                    # Validate email
                    if not validate_email(email):
                        st.error("Please enter a valid email address")
                    elif password != confirm_password:
                        st.error("Passwords do not match")
                    else:
                        # Validate password strength
                        is_valid, message = validate_password(password)
                        if not is_valid:
                            st.error(message)
                        else:
                            success, message = register_user(email, password, name, company)
                            if success:
                                st.success(message)
                                # Redirect to home page after successful registration
                                st.session_state.current_page = "Home"
                                st.rerun()
                            else:
                                st.error(message)
                else:
                    st.warning("Please fill in all required fields")
                    
        st.markdown("Already have an account? [Login here](#)")
        if st.button("Login Instead"):
            st.session_state.current_page = "Login"
            st.rerun()

def show_subscription_status():
    """Show the user's current subscription status"""
    if st.session_state.subscription_type == 'free':
        # Free tier status
        st.markdown("""
        <div class="card">
        <h4>📊 Free Tier Status</h4>
        <p>You are currently on the Free tier with limited features.</p>
        <p>Today's usage:</p>
        <ul>
            <li>Reports: {}/{}  </li>
            <li>Queries: {}/{}</li>
            <li>Analyses: {}/{}</li>
            <li>Generations: {}/{}</li>
        </ul>
        </div>
        """.format(
            st.session_state.usage_counts.get('reports', 0), FREE_TIER_LIMITS['reports_per_day'],
            st.session_state.usage_counts.get('queries', 0), FREE_TIER_LIMITS['queries_per_day'],
            st.session_state.usage_counts.get('analysis', 0), FREE_TIER_LIMITS['analysis_per_day'],
            st.session_state.usage_counts.get('generation', 0), FREE_TIER_LIMITS['generation_per_day']
        ), unsafe_allow_html=True)
    else:
        # Premium tier status
        st.markdown("""
        <div class="card" style="background-color: #e8f5e9; border-left-color: #4caf50;">
        <h4>💎 Premium Tier</h4>
        <p>You are enjoying unlimited access to all premium features!</p>
        <p>Next billing date: July 15, 2023</p>
        </div>
        """, unsafe_allow_html=True)

def show_upgrade_popup():
    """Show popup when user reaches usage limits"""
    st.sidebar.markdown("""
    <div class="upgrade-banner">
    <h4>⚠️ Usage Limit Reached</h4>
    <p>You've reached your free tier usage limit for today.</p>
    <p>Upgrade to Premium for unlimited usage!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Button to show payment interface
    if st.sidebar.button("Upgrade to Premium", key="upgrade_popup_btn"):
        st.session_state.show_payment = True
        st.session_state.show_upgrade_popup = False
    
    # Button to dismiss popup
    if st.sidebar.button("Dismiss", key="dismiss_popup_btn"):
        st.session_state.show_upgrade_popup = False
        st.rerun()

def show_payment_interface():
    """Show payment interface for subscription upgrade"""
    st.title("Upgrade to Premium")
    
    st.markdown("""
    <div class="card" style="background-color: #e8f5e9; border-left-color: #4caf50;">
    <h3>Premium Plan - $29.99/month</h3>
    <p>Unlock full access to all premium features:</p>
    <ul>
        <li>Unlimited contract analyses</li>
        <li>Unlimited reports & queries</li>
        <li>Advanced clause analysis</li>
        <li>Unlimited reminders</li>
        <li>SMS notifications</li>
        <li>Priority support</li>
        <li>Batch processing</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Payment form
    with st.form("payment_form"):
        st.markdown("### Payment Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            card_name = st.text_input("Name on Card")
            card_number = st.text_input("Card Number")
            
        with col2:
            expiry = st.text_input("Expiration Date (MM/YY)")
            cvv = st.text_input("CVV", type="password")
        
        # Billing information
        st.markdown("### Billing Address")
        address = st.text_input("Address")
        city = st.text_input("City")
        
        col3, col4 = st.columns(2)
        
        with col3:
            state = st.text_input("State/Province")
        
        with col4:
            zip_code = st.text_input("ZIP/Postal Code")
            
        country = st.selectbox("Country", ["United States", "Canada", "United Kingdom", "Australia", "Other"])
        
        # Terms and conditions
        agree = st.checkbox("I agree to the terms and conditions")
        
        submitted = st.form_submit_button("Complete Payment")
        
        if submitted:
            if card_name and card_number and expiry and cvv and address and city and state and zip_code and agree:
                # For demo purposes, just upgrade the account
                st.session_state.subscription_type = 'paid'
                st.success("Payment successful! Your account has been upgraded to Premium.")
                
                # Update user record in session state
                if 'users' in st.session_state and st.session_state.email in st.session_state.users:
                    user_data = st.session_state.users[st.session_state.email]
                    user_data['subscription_type'] = 'paid'
                    st.session_state.users[st.session_state.email] = user_data
                
                # Hide payment interface
                st.session_state.show_payment = False
                
                # Redirect to home page
                st.session_state.current_page = "Home"
                st.rerun()
            else:
                st.error("Please fill in all required fields and agree to the terms and conditions")
    
    # Cancel button
    if st.button("Cancel"):
        st.session_state.show_payment = False
        st.rerun()
