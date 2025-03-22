# FileCheckMaster

FileCheckMaster is a comprehensive contract management and reminder system that helps you track, manage, and receive notifications about important contracts and files.

## Features

- Contract tracking and management
- SMS notifications for important deadlines
- Authentication system
- Automated reminders
- File status monitoring
- User management system

## Prerequisites

- Python 3.x
- PostgreSQL database
- SMS service provider credentials (for notifications)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/FileCheckMaster.git
cd FileCheckMaster
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env` file:
```
DATABASE_URL=your_database_url
SMS_API_KEY=your_sms_api_key
SECRET_KEY=your_secret_key
```

4. Initialize the database:
```bash
python create_tables.py
```

## Project Structure

- `app.py` - Main application file containing the core functionality
- `auth.py` - Authentication and user management system
- `contract_reminders.py` - Contract reminder and notification logic
- `sms_notifications.py` - SMS notification handling
- `create_tables.py` - Database initialization and schema creation

## Usage

1. Start the application:
```bash
python app.py
```

2. Access the web interface through your browser at `http://localhost:5000`

3. Log in with your credentials to:
   - Manage contracts and files
   - Set up reminders
   - Configure notifications
   - Track contract statuses

## Configuration

The application can be configured through the `.env` file. Key configuration options include:

- Database connection settings
- SMS notification parameters
- Security settings
- Reminder intervals

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the development team. 
