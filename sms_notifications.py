import os
import streamlit as st
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv()

# Email configuration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def format_reminder_message(reminder_data):
    """
    Format a reminder notification message
    
    Args:
        reminder_data (dict): Reminder data dictionary
        
    Returns:
        str: Formatted message for notifications
    """
    # Format the date
    if isinstance(reminder_data['reminder_date'], str):
        date_str = reminder_data['reminder_date']
    else:
        date_str = reminder_data['reminder_date'].strftime('%Y-%m-%d')
        
    return (
        f"⚖️ CONTRACT REMINDER ⚖️\n\n"
        f"Contract: {reminder_data['contract_name']}\n"
        f"Deadline: {date_str}\n"
        f"{reminder_data['description']}\n\n"
        "View more details in Legal Contract Analysis System"
    )

def send_email_notification(to_email, subject, message_text):
    """
    Send an email notification
    
    Args:
        to_email (str): Recipient's email address
        subject (str): Email subject
        message_text (str): Message text to send
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Check if email credentials are configured
    if not all([EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD]):
        st.warning("Email is not properly configured. Email notifications are disabled.")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Format HTML body
        formatted_message = message_text.replace('\n', '<br>')
        body = f"""
        <html>
        <body>
            <h2>{subject}</h2>
            <p>{formatted_message}</p>
            <p>Best regards,<br>
            Legal Contract Analysis Team</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"Email notification sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"Error sending email notification: {str(e)}")
        return False

def send_reminder_notification(reminder_data, user_email):
    """
    Send a reminder notification for a contract deadline via email
    
    Args:
        reminder_data (dict): Reminder data dictionary
        user_email (str): Email address to send to
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not user_email:
        return False
        
    # Format the message
    message = format_reminder_message(reminder_data)
    subject = f"Contract Reminder: {reminder_data['contract_name']}"
    
    # Send the email
    return send_email_notification(user_email, subject, message)

def show_notification_settings():
    """Display and manage email notification settings in Streamlit"""
    st.subheader("Email Notification Settings")
    
    # Get current settings from session state or initialize
    if 'email_notifications_enabled' not in st.session_state:
        st.session_state.email_notifications_enabled = True
    
    # Toggle for enabling/disabling notifications
    notifications_enabled = st.checkbox(
        "Enable email notifications for contract deadlines", 
        value=st.session_state.email_notifications_enabled
    )
    
    if notifications_enabled:
        st.markdown("""
        <div class="card">
        <p>Email notifications will alert you about upcoming contract deadlines.</p>
        <p>Notifications will be sent to your registered email address.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Save Notification Settings", use_container_width=True):
            st.session_state.email_notifications_enabled = True
            st.success("Email notification settings saved successfully!")
            
        # Test button
        if st.button("Send Test Email", use_container_width=True):
            if hasattr(st.session_state, 'email') and st.session_state.email:
                test_sent = send_email_notification(
                    st.session_state.email,
                    "Test Notification from Legal Contract Analysis System",
                    "This is a test notification. Your email notifications are set up correctly!"
                )
                if test_sent:
                    st.success("Test email sent successfully!")
                else:
                    st.error("Failed to send test email. Please check email configuration.")
            else:
                st.error("No email address available. Please make sure you're logged in.")
    else:
        # If notifications are disabled
        st.session_state.email_notifications_enabled = False
        
    # Show premium upgrade message for free tier users
    if st.session_state.subscription_type == 'free':
        st.markdown("""
        <div class="card">
        <h4>📧 Email Notification Limits</h4>
        <p>Free tier users are limited to 10 email notifications per month.</p>
        <p>Upgrade to Premium for unlimited email notifications!</p>
        </div>
        """, unsafe_allow_html=True)
