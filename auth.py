import streamlit as st
import supabase
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import streamlit as st
import supabase
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid
import re
# First Streamlit command - must be at the very top
st.set_page_config(page_title="Contract Analysis System", layout="wide")

# Get the current directory
CURRENT_DIR = Path(__file__).parent

# Load environment variables
load_dotenv(CURRENT_DIR / '.env')

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase_client = supabase.create_client(supabase_url, supabase_key)

# Define usage limits for free tier
FREE_TIER_LIMITS = {
    'reports_per_day': 3,
    'queries_per_day': 10,
    'analysis_per_day': 5
}

def init_session_state():
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

def reset_daily_counts():
    today = datetime.now().date()
    if (st.session_state.usage_counts['last_reset'] != today):
        st.session_state.usage_counts = {
            'reports': 0,
            'queries': 0,
            'analysis': 0,
            'last_reset': today
        }

def check_usage_limits(action_type):
    if st.session_state.subscription_type == 'paid':
        return True
    
    reset_daily_counts()
    
    limits = {
        'reports': FREE_TIER_LIMITS['reports_per_day'],
        'queries': FREE_TIER_LIMITS['queries_per_day'],
        'analysis': FREE_TIER_LIMITS['analysis_per_day']
    }
    
    if st.session_state.usage_counts[action_type] >= limits[action_type]:
        st.session_state.show_upgrade_popup = True
        return False
    
    st.session_state.usage_counts[action_type] += 1
    return True

def submit_support_ticket(subject, description, category):
    try:
        ticket_data = {
            'user_id': st.session_state.user.id,
            'email': st.session_state.user.email,
            'subject': subject,
            'description': description,
            'category': category,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'ticket_id': str(uuid.uuid4())
        }
        
        response = supabase_client.table('support_tickets').insert(ticket_data).execute()
        return True, "Support ticket submitted successfully!"
    except Exception as e:
        return False, f"Error submitting ticket: {str(e)}"

def submit_review(rating, review_text):
    try:
        review_data = {
            'user_id': st.session_state.user.id,
            'email': st.session_state.user.email,
            'rating': rating,
            'review': review_text,
            'created_at': datetime.now().isoformat()
        }
        
        response = supabase_client.table('reviews').insert(review_data).execute()
        return True, "Review submitted successfully!"
    except Exception as e:
        return False, f"Error submitting review: {str(e)}"

def get_user_tickets():
    try:
        response = supabase_client.table('support_tickets')\
            .select('*')\
            .eq('user_id', st.session_state.user.id)\
            .execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching tickets: {str(e)}")
        return []

def show_support_interface():
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
                        st.session_state.support_tab = 'My Tickets'
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill in all required fields.")

        elif selected_tab == "My Tickets":
            st.header("My Support Tickets")
            tickets = get_user_tickets()
            
            if tickets:
                for ticket in tickets:
                    with st.expander(f"Ticket: {ticket['subject']} ({ticket['status'].upper()})"):
                        st.write(f"**Category:** {ticket['category']}")
                        st.write(f"**Created:** {ticket['created_at'][:10]}")
                        st.write(f"**Description:**")
                        st.write(ticket['description'])
                        st.write(f"**Status:** {ticket['status'].upper()}")
                        if ticket.get('response'):
                            st.write("**Support Response:**")
                            st.write(ticket['response'])
            else:
                st.info("No support tickets found.")

        elif selected_tab == "Rate & Review":
            st.header("Rate Our Service")
            
            rating = st.slider("Rating", 1, 5, 5)
            review_text = st.text_area("Your Review", height=100)
            
            if st.button("Submit Review"):
                if review_text:
                    success, message = submit_review(rating, review_text)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.warning("Please write a review before submitting.")

def validate_credit_card(number, expiry, cvv):
    # Basic validation
    if not number or not expiry or not cvv:
        return False, "All fields are required"
    
    # Check card number (simple check for 16 digits)
    if not re.match(r'^\d{16}$', number.replace(' ', '')):
        return False, "Invalid card number"
    
    # Check expiry format (MM/YY)
    if not re.match(r'^\d{2}/\d{2}$', expiry):
        return False, "Invalid expiry date format (MM/YY)"
    
    # Check CVV (3 or 4 digits)
    if not re.match(r'^\d{3,4}$', cvv):
        return False, "Invalid CVV"
    
    return True, "Valid"

def validate_upi(upi_id):
    # Basic UPI ID validation
    if not re.match(r'^[\w\.\-]+@[\w\-]+$', upi_id):
        return False, "Invalid UPI ID format"
    return True, "Valid"

def process_payment(payment_method, payment_data):
    try:
        # In a real application, this would integrate with a payment processor
        # For demo purposes, we'll simulate a successful payment
        
        payment_record = {
            'user_id': st.session_state.user.id,
            'amount': 999,  # Example price
            'payment_method': payment_method,
            'transaction_id': str(uuid.uuid4()),
            'status': 'completed',
            'created_at': datetime.now().isoformat()
        }
        
        # Store payment record in Supabase
        response = supabase_client.table('payments').insert(payment_record).execute()
        
        # Update user subscription
        user_update = {
            'subscription_type': 'paid',
            'subscription_start': datetime.now().isoformat(),
            'subscription_end': (datetime.now() + timedelta(days=365)).isoformat()
        }
        supabase_client.table('users').update(user_update).eq('id', st.session_state.user.id).execute()
        
        st.session_state.subscription_type = 'paid'
        return True, "Payment successful!"
    except Exception as e:
        return False, f"Payment failed: {str(e)}"

def show_payment_interface():
    st.header("Upgrade to Premium")
    st.write("### 💎 Premium Plan - $9.99/month")
    st.write("""
    - ✅ Unlimited Reports
    - ✅ Unlimited Queries
    - ✅ Unlimited Analysis
    - ✅ Priority Support
    - ✅ Advanced Features
    """)
    
    payment_method = st.radio("Select Payment Method", ["Credit Card", "UPI"])
    
    if payment_method == "Credit Card":
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            card_number = st.text_input("Card Number", placeholder="1234 5678 9012 3456")
        with col2:
            expiry = st.text_input("Expiry (MM/YY)", placeholder="12/25")
        with col3:
            cvv = st.text_input("CVV", type="password", placeholder="123")
        
        cardholder = st.text_input("Cardholder Name")
        
        if st.button("Pay Now"):
            valid, message = validate_credit_card(
                card_number.replace(' ', ''), 
                expiry, 
                cvv
            )
            if valid:
                success, message = process_payment('credit_card', {
                    'card_number': card_number,
                    'expiry': expiry,
                    'cardholder': cardholder
                })
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error(message)
    
    else:  # UPI
        upi_id = st.text_input("Enter UPI ID", placeholder="username@upi")
        
        if st.button("Pay Now"):
            valid, message = validate_upi(upi_id)
            if valid:
                success, message = process_payment('upi', {
                    'upi_id': upi_id
                })
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error(message)

def show_upgrade_popup():
    if st.session_state.show_upgrade_popup:
        with st.sidebar:
            st.error("⚠️ Free Tier Limit Reached!")
            st.info("""
            ### Upgrade to Premium! 🌟
            Get unlimited access to:
            - Unlimited Reports
            - Unlimited Queries
            - Unlimited Analysis
            - Priority Support
            - Advanced Features
            """)
            
            if st.button("Upgrade Now"):
                st.session_state.show_payment = True
                st.session_state.show_upgrade_popup = False
            
            if st.button("Maybe Later"):
                st.session_state.show_upgrade_popup = False

def show_subscription_status():
    with st.sidebar:
        st.write("---")
        st.write("### Subscription Status")
        if st.session_state.subscription_type == 'free':
            st.write("🔵 Free Tier")
            st.write(f"Reports Today: {st.session_state.usage_counts['reports']}/{FREE_TIER_LIMITS['reports_per_day']}")
            st.write(f"Queries Today: {st.session_state.usage_counts['queries']}/{FREE_TIER_LIMITS['queries_per_day']}")
            st.write(f"Analysis Today: {st.session_state.usage_counts['analysis']}/{FREE_TIER_LIMITS['analysis_per_day']}")
            
            if st.button("Upgrade to Premium 🌟"):
                st.session_state.show_upgrade_popup = True
        else:
            st.write("💎 Premium Tier")
            st.write("Unlimited Access")

def login(email, password):
    try:
        response = supabase_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.session_state.user = response.user
        st.session_state.authenticated = True
        st.session_state.subscription_type = 'free'
        return True
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

def signup(email, password):
    try:
        response = supabase_client.auth.sign_up({
            "email": email,
            "password": password
        })
        st.success("Signup successful! Please check your email for verification.")
        return True
    except Exception as e:
        st.error(f"Signup failed: {str(e)}")
        return False

def logout():
    try:
        supabase_client.auth.sign_out()
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.subscription_type = 'free'
        st.session_state.usage_counts = {
            'reports': 0,
            'queries': 0,
            'analysis': 0,
            'last_reset': datetime.now().date()
        }
    except Exception as e:
        st.error(f"Logout failed: {str(e)}")

def load_main_app():
    try:
        sys.path.append(str(CURRENT_DIR))
        
        class CustomStreamlit:
            def __init__(self, real_streamlit):
                self._st = real_streamlit
            
            def set_page_config(self, *args, **kwargs):
                pass
            
            def __getattr__(self, name):
                return getattr(self._st, name)
        
        original_st = sys.modules['streamlit']
        sys.modules['streamlit'] = CustomStreamlit(original_st)
        
        import app
        
        sys.modules['streamlit'] = original_st
        
        if hasattr(app, 'main'):
            app.main()
        
    except Exception as e:
        st.error(f"Error loading main app: {str(e)}")
        import traceback
        st.error(traceback.format_exc())

def main():
    init_session_state()
    
    if 'show_payment' not in st.session_state:
        st.session_state.show_payment = False

    if st.session_state.authenticated:
        with st.sidebar:
            st.write(f"Logged in as: {st.session_state.user.email}")
            if st.button("Logout"):
                logout()
                st.rerun()
        
        show_support_interface()
        show_subscription_status()
        show_upgrade_popup()

        if st.session_state.show_payment:
            show_payment_interface()
        elif not st.session_state.show_support:
            load_main_app()
    else:
        # [Login/signup code remains the same]
        st.title("Login to Contract Analysis System")
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            st.header("Login")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login"):
                if login(email, password):
                    st.rerun()

        with tab2:
            st.header("Sign Up")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            if st.button("Sign Up"):
                if password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    if signup(email, password):
                        st.info("Please login after verifying your email.")

if __name__ == "__main__":
    main()