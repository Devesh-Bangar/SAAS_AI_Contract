import streamlit as st
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import threading
import time
# Rename file but keep same function names for compatibility
from sms_notifications import send_reminder_notification, show_notification_settings
import uuid

# Load environment variables
load_dotenv()

# Global variables for background thread
reminder_thread = None
stop_thread = False

# Initialize database connection
def get_db_connection():
    """Get connection to PostgreSQL database via Supabase"""
    try:
        # We'll return None as we're now using Supabase client API directly
        # But this function needs to exist for backward compatibility
        
        # Create a fallback in-memory storage for demo purposes
        if 'reminders_db' not in st.session_state:
            st.session_state.reminders_db = []
        
        print("Using session storage for reminders")
        return None
    except Exception as e:
        st.error(f"Database connection error: {str(e)}")
        # Create a fallback in-memory storage for demo purposes
        if 'reminders_db' not in st.session_state:
            st.session_state.reminders_db = []
        return None

def add_reminders_to_app():
    """Adds contract reminders functionality to the application"""
    # Start background reminder service if not already running
    global reminder_thread
    if not reminder_thread or not reminder_thread.is_alive():
        start_reminder_service()
    
    # Check if user is logged in
    if not st.session_state.authenticated:
        st.warning("Please log in or register to access contract reminders.")
        
        # Add a button to go to login page
        if st.button("Go to Login / Register"):
            st.session_state.current_page = "Login"
            st.rerun()
        return
    
    # Load user notification settings if not already loaded
    if hasattr(st.session_state, 'email') and st.session_state.email:
        if (not hasattr(st.session_state, 'sms_notifications_enabled') or 
            not hasattr(st.session_state, 'phone_number')):
            load_notification_settings(st.session_state.email)
    
    st.title("Contract Reminders & Calendar")
    
    # Subscription info
    if st.session_state.subscription_type == 'free':
        st.markdown("""
        <div class="card">
        <h4>Free Tier Reminder Features</h4>
        <ul>
            <li>Basic reminder capabilities</li>
            <li>Limited to 10 reminders</li>
            <li>SMS notifications limited to 5 per month</li>
        </ul>
        <p>Need more? Upgrade to Premium for unlimited reminders and notifications!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="card" style="background-color: #e8f5e9; border-left-color: #4caf50;">
        <h4>💎 Premium Tier Activated</h4>
        <p>You have access to unlimited reminders and premium features!</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Create tabs for different reminder views
    reminder_tabs = st.tabs(["Upcoming", "Add New", "Calendar View", "Notifications"])
    
    with reminder_tabs[0]:
        show_upcoming_reminders()
    
    with reminder_tabs[1]:
        add_new_reminder()
    
    with reminder_tabs[2]:
        show_calendar_view()
        
    with reminder_tabs[3]:
        show_notification_settings()
        
    # Store user notification settings in database when they're updated
    if hasattr(st.session_state, 'email') and st.session_state.email and \
       hasattr(st.session_state, 'sms_notifications_enabled') and \
       hasattr(st.session_state, 'phone_number'):
        store_notification_settings(
            st.session_state.email,
            st.session_state.phone_number,
            st.session_state.sms_notifications_enabled
        )

def show_upcoming_reminders():
    """Display upcoming reminders for the user"""
    st.subheader("Upcoming Contract Deadlines")
    
    if not st.session_state.authenticated:
        st.info("Please log in to view your reminders.")
        return
    
    try:
        # Use session state storage
        if 'reminders_db' in st.session_state:
            reminders = [r for r in st.session_state.reminders_db 
                        if r['user_email'] == st.session_state.email and r['status'] == 'pending']
            reminders.sort(key=lambda x: x['reminder_date'])
        else:
            reminders = []
        
        if not reminders:
            st.info("No upcoming reminders. Add new reminders to stay on top of important contract dates.")
            return
        
        # Group reminders by urgency
        today = datetime.now().date()
        urgent_reminders = []
        upcoming_reminders = []
        future_reminders = []
        
        for reminder in reminders:
            due_date = reminder['reminder_date']
            # Ensure due_date is a date object
            if isinstance(due_date, str):
                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
                
            days_remaining = (due_date - today).days
            
            if days_remaining < 7:
                urgent_reminders.append((reminder, days_remaining))
            elif days_remaining < 30:
                upcoming_reminders.append((reminder, days_remaining))
            else:
                future_reminders.append((reminder, days_remaining))
        
        # Display urgent reminders
        if urgent_reminders:
            st.markdown("### ⚠️ Urgent (Next 7 days)")
            for reminder, days in urgent_reminders:
                with st.expander(f"**{reminder['contract_name']}** - {days} days remaining"):
                    st.markdown(f"""
                    <div class="risk-high">
                    <strong>Contract:</strong> {reminder['contract_name']}<br>
                    <strong>Due Date:</strong> {reminder['reminder_date'].strftime('%Y-%m-%d') if isinstance(reminder['reminder_date'], datetime) else reminder['reminder_date']}<br>
                    <strong>Details:</strong> {reminder['description']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Mark Complete", key=f"complete_{reminder['id']}"):
                            mark_reminder_complete(reminder['id'])
                            st.rerun()
                    with col2:
                        if st.button("🔔 Snooze 7 days", key=f"snooze_{reminder['id']}"):
                            snooze_reminder(reminder['id'], 7)
                            st.rerun()
        
        # Display upcoming reminders
        if upcoming_reminders:
            st.markdown("### 🔶 Upcoming (Next 30 days)")
            for reminder, days in upcoming_reminders:
                with st.expander(f"**{reminder['contract_name']}** - {days} days remaining"):
                    st.markdown(f"""
                    <div class="risk-medium">
                    <strong>Contract:</strong> {reminder['contract_name']}<br>
                    <strong>Due Date:</strong> {reminder['reminder_date'].strftime('%Y-%m-%d') if isinstance(reminder['reminder_date'], datetime) else reminder['reminder_date']}<br>
                    <strong>Details:</strong> {reminder['description']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Mark Complete", key=f"complete_{reminder['id']}"):
                            mark_reminder_complete(reminder['id'])
                            st.rerun()
                    with col2:
                        if st.button("🔔 Snooze 14 days", key=f"snooze_{reminder['id']}"):
                            snooze_reminder(reminder['id'], 14)
                            st.rerun()
        
        # Display future reminders
        if future_reminders:
            st.markdown("### 📅 Future")
            for reminder, days in future_reminders:
                with st.expander(f"**{reminder['contract_name']}** - {days} days remaining"):
                    st.markdown(f"""
                    <div class="risk-low">
                    <strong>Contract:</strong> {reminder['contract_name']}<br>
                    <strong>Due Date:</strong> {reminder['reminder_date'].strftime('%Y-%m-%d') if isinstance(reminder['reminder_date'], datetime) else reminder['reminder_date']}<br>
                    <strong>Details:</strong> {reminder['description']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Mark Complete", key=f"complete_{reminder['id']}"):
                            mark_reminder_complete(reminder['id'])
                            st.rerun()
                    with col2:
                        if st.button("🔔 Snooze 30 days", key=f"snooze_{reminder['id']}"):
                            snooze_reminder(reminder['id'], 30)
                            st.rerun()
                            
    except Exception as e:
        st.error(f"Error loading reminders: {str(e)}")

def add_new_reminder():
    """Form to add a new contract reminder"""
    st.subheader("Add New Reminder")
    
    if not st.session_state.authenticated:
        st.info("Please log in to add reminders.")
        return
    
    with st.form("new_reminder_form"):
        contract_name = st.text_input("Contract Name", placeholder="E.g., Service Agreement with ABC Corp")
        
        col1, col2 = st.columns(2)
        with col1:
            reminder_date = st.date_input("Due Date", min_value=datetime.now().date())
        with col2:
            reminder_type = st.selectbox("Reminder Type", [
                "Renewal", "Payment", "Deadline", "Review", "Other"
            ])
        
        description = st.text_area("Details", placeholder="Additional details about this reminder")
        
        submitted = st.form_submit_button("Add Reminder")
        
        if submitted:
            if contract_name and description:
                try:
                    # Using session state storage for reminders
                    if 'reminders_db' not in st.session_state:
                        st.session_state.reminders_db = []
                        
                    # Generate a unique ID
                    reminder_id = str(uuid.uuid4())
                    
                    # Add reminder to session state
                    st.session_state.reminders_db.append({
                        'id': reminder_id,
                        'user_email': st.session_state.email,
                        'contract_name': contract_name,
                        'reminder_date': reminder_date,
                        'description': description,
                        'status': 'pending',
                        'reminder_type': reminder_type
                    })
                    
                    # Send email notification if enabled
                    if hasattr(st.session_state, 'email_notifications_enabled') and st.session_state.email_notifications_enabled:
                        from sms_notifications import send_reminder_notification
                        
                        reminder_data = {
                            'contract_name': contract_name,
                            'reminder_date': reminder_date,
                            'description': description
                        }
                        
                        # Actually send the notification
                        if hasattr(st.session_state, 'email') and st.session_state.email:
                            send_reminder_notification(reminder_data, st.session_state.email)
                    
                    st.success(f"Reminder added for {contract_name} on {reminder_date}")
                    
                except Exception as e:
                    st.error(f"Error adding reminder: {str(e)}")
            else:
                st.warning("Please enter both contract name and details.")

def mark_reminder_complete(reminder_id):
    """Mark a reminder as completed"""
    try:
        # Use session state storage
        if 'reminders_db' in st.session_state:
            for i, reminder in enumerate(st.session_state.reminders_db):
                if reminder['id'] == reminder_id:
                    st.session_state.reminders_db[i]['status'] = 'completed'
                    break
        
        return True
    except Exception as e:
        st.error(f"Error updating reminder: {str(e)}")
        return False

def snooze_reminder(reminder_id, days):
    """Snooze a reminder by specified number of days"""
    try:
        # Use session state storage
        if 'reminders_db' in st.session_state:
            for i, reminder in enumerate(st.session_state.reminders_db):
                if reminder['id'] == reminder_id:
                    current_date = reminder['reminder_date']
                    # Handle both datetime and date objects
                    if isinstance(current_date, str):
                        current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
                    new_date = current_date + timedelta(days=days)
                    st.session_state.reminders_db[i]['reminder_date'] = new_date
                    break
        
        return True
    except Exception as e:
        st.error(f"Error snoozing reminder: {str(e)}")
        return False

def show_calendar_view():
    """Display reminders in a calendar format"""
    st.subheader("Calendar View")
    
    if not st.session_state.authenticated:
        st.info("Please log in to view your reminder calendar.")
        return
    
    # Get all active reminders
    try:
        # Use session state storage
        if 'reminders_db' in st.session_state:
            reminders = [r for r in st.session_state.reminders_db 
                         if r['user_email'] == st.session_state.email and r['status'] == 'pending']
            reminders.sort(key=lambda x: x['reminder_date'])
        else:
            reminders = []
        
        if not reminders:
            st.info("No reminders to display in the calendar. Add new reminders to see them here.")
            return
        
        # Group reminders by month
        reminders_by_month = {}
        
        for reminder in reminders:
            due_date = reminder['reminder_date']
            
            # Ensure due_date is a date object
            if isinstance(due_date, str):
                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
                
            month_key = due_date.strftime("%Y-%m")
            month_name = due_date.strftime("%B %Y")
            
            if month_name not in reminders_by_month:
                reminders_by_month[month_name] = []
                
            reminders_by_month[month_name].append(reminder)
        
        # Display reminders grouped by month
        for month_name, month_reminders in sorted(reminders_by_month.items()):
            with st.expander(f"📅 {month_name}", expanded=True):
                # Create a calendar grid
                days_in_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                
                # Get the first day of this month
                first_reminder_date = month_reminders[0]['reminder_date']
                if isinstance(first_reminder_date, str):
                    first_reminder_date = datetime.strptime(first_reminder_date, "%Y-%m-%d").date()
                
                year = first_reminder_date.year
                month = first_reminder_date.month
                
                # Get first day of the month and determine the weekday (0 is Monday in our grid)
                first_day = datetime(year, month, 1).date()
                first_weekday = first_day.weekday()  # 0 = Monday, 6 = Sunday
                
                # Get last day of the month
                if month == 12:
                    last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
                
                # Calculate number of days in the month and how many calendar rows we need
                days_in_month = last_day.day
                
                # Create the calendar header
                cols = st.columns(7)
                for i, day_name in enumerate(days_in_week):
                    cols[i].markdown(f"<div style='text-align: center;'><strong>{day_name}</strong></div>", unsafe_allow_html=True)
                
                # Counter for the day of the month
                current_day = 1
                
                # Create the calendar grid
                # Calculate how many rows we need (weeks)
                num_rows = (first_weekday + days_in_month + 6) // 7
                
                for row in range(num_rows):
                    cols = st.columns(7)
                    
                    for col in range(7):
                        if (row == 0 and col < first_weekday) or current_day > days_in_month:
                            # Empty cells before the 1st of the month or after the last day
                            cols[col].markdown("&nbsp;", unsafe_allow_html=True)
                        else:
                            # Regular day cell
                            date_obj = datetime(year, month, current_day).date()
                            
                            # Check if there are any reminders for this day
                            day_reminders = [r for r in month_reminders if (
                                isinstance(r['reminder_date'], datetime) and r['reminder_date'].date() == date_obj
                            ) or (
                                isinstance(r['reminder_date'], type(date_obj)) and r['reminder_date'] == date_obj
                            )]
                            
                            if day_reminders:
                                # Day with reminders
                                reminder_count = len(day_reminders)
                                cols[col].markdown(
                                    f"<div style='text-align: center; background-color: #e3f2fd; "
                                    f"border-radius: 50%; padding: 5px;'>"
                                    f"<strong>{current_day}</strong><br>"
                                    f"<span style='color: #1565C0;'>{reminder_count} item{'s' if reminder_count > 1 else ''}</span>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )
                                
                                # Create a tooltip or popup to show the reminders
                                if cols[col].button(f"View", key=f"view_{month}_{current_day}"):
                                    st.session_state.selected_date = date_obj
                                    st.session_state.selected_reminders = day_reminders
                            else:
                                # Regular day without reminders
                                cols[col].markdown(
                                    f"<div style='text-align: center; padding: 5px;'>{current_day}</div>",
                                    unsafe_allow_html=True
                                )
                            
                            current_day += 1
                
                # If a date with reminders was selected, show the reminders
                if hasattr(st.session_state, 'selected_date') and hasattr(st.session_state, 'selected_reminders'):
                    st.markdown(f"### Reminders for {st.session_state.selected_date.strftime('%B %d, %Y')}")
                    
                    for reminder in st.session_state.selected_reminders:
                        st.markdown(f"""
                        <div class="card">
                        <strong>{reminder['contract_name']}</strong><br>
                        {reminder['description']}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    if st.button("Close", key="close_date_view"):
                        del st.session_state.selected_date
                        del st.session_state.selected_reminders
                        st.rerun()
            
    except Exception as e:
        st.error(f"Error displaying calendar: {str(e)}")

def start_reminder_service():
    """Start a background thread to check for and send reminders"""
    global reminder_thread, stop_thread
    
    def check_reminders():
        """Function to run in background thread to check for due reminders"""
        while not stop_thread:
            try:
                # Get current time
                now = datetime.now()
                today = now.date()
                
                # Use session state only
                if 'reminders_db' in st.session_state:
                    for reminder in st.session_state.reminders_db:
                        if reminder['status'] == 'pending':
                            due_date = reminder['reminder_date']
                            # Convert to date object if it's a string
                            if isinstance(due_date, str):
                                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
                            
                            # Check if due within next 24 hours
                            if today <= due_date <= (today + timedelta(days=1)):
                                # Check if notification already sent
                                notification_sent = reminder.get('notification_sent_on', None)
                                if not notification_sent or (isinstance(notification_sent, str) and 
                                                          datetime.strptime(notification_sent, "%Y-%m-%d").date() < today):
                                    # Get user email
                                    user_email = reminder['user_email']
                                    
                                    # Get user settings
                                    if ('notification_settings' in st.session_state and 
                                        user_email in st.session_state.notification_settings):
                                        
                                        # Send email notification instead
                                        reminder_data = {
                                            'contract_name': reminder['contract_name'],
                                            'reminder_date': reminder['reminder_date'],
                                            'description': reminder['description']
                                        }
                                        
                                        success = send_reminder_notification(
                                            reminder_data, 
                                            user_email
                                        )
                                        
                                        # Update sent timestamp
                                        if success:
                                            for i, rem in enumerate(st.session_state.reminders_db):
                                                if rem['id'] == reminder['id']:
                                                    st.session_state.reminders_db[i]['notification_sent_on'] = today.strftime("%Y-%m-%d")
                                                    break
                
            except Exception as e:
                print(f"Error in reminder service: {str(e)}")
            
            # Sleep for a while before checking again (e.g., every 15 minutes)
            time.sleep(900)  # 15 minutes
    
    # Initialize and start the thread
    stop_thread = False
    reminder_thread = threading.Thread(target=check_reminders, daemon=True)
    reminder_thread.start()

def stop_reminder_service():
    """Stop the reminder service background thread"""
    global stop_thread
    stop_thread = True

def store_notification_settings(email, phone_number, sms_enabled):
    """Store user notification settings"""
    try:
        # Store in session state
        if 'notification_settings' not in st.session_state:
            st.session_state.notification_settings = {}
        
        st.session_state.notification_settings[email] = {
            'phone_number': phone_number,
            'sms_enabled': sms_enabled,
            'updated_at': datetime.now().isoformat()
        }
        
        return True
    except Exception as e:
        print(f"Error storing notification settings: {str(e)}")
        return False

def load_notification_settings(email):
    """Load user notification settings"""
    try:
        # Load from session state
        if ('notification_settings' in st.session_state and 
            email in st.session_state.notification_settings):
            settings = st.session_state.notification_settings[email]
            
            st.session_state.phone_number = settings.get('phone_number', '')
            st.session_state.sms_notifications_enabled = settings.get('sms_enabled', False)
            return True
        
        # Default settings if not found
        st.session_state.phone_number = ''
        st.session_state.sms_notifications_enabled = False
        return False
    
    except Exception as e:
        print(f"Error loading notification settings: {str(e)}")
        # Default settings if error
        st.session_state.phone_number = ''
        st.session_state.sms_notifications_enabled = False
        return False
