# Setup Guide

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 18+
- PostgreSQL
- Redis (optional, for Celery)

### Backend Setup

1. **Navigate to backend:**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

5. **Run migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   # Or use the sample data command which creates one
   ```

7. **Load sample data (optional):**
   ```bash
   python manage.py load_sample_data
   ```

8. **Run server:**
   ```bash
   python manage.py runserver
   ```

### Frontend Setup

1. **Navigate to frontend:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

## Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs/
- Django Admin: http://localhost:8000/admin/

## Default Credentials (after loading sample data)

- **Master Admin:**
  - Email: admin@timetable.com
  - Password: admin123

- **College Admin:**
  - Email: admin@democollege.com
  - Password: admin123

- **Teachers:**
  - Email: teacher1@demo.com, teacher2@demo.com, etc.
  - Password: teacher123

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL is running
- Check database credentials in `.env`
- Verify database exists: `createdb timetable_db`

### Frontend Build Issues
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check Node.js version: `node --version` (should be 18+)

### Import Errors
- Ensure all dependencies are installed
- Check Python virtual environment is activated
- Verify all migrations are applied

## Next Steps

1. Create your first college via Master Admin dashboard
2. Add departments, teachers, subjects, and sections
3. Generate your first timetable
4. Customize the algorithm parameters as needed
