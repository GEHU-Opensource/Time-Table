# Timetable Management System

A comprehensive, scalable timetable management system with multi-tenant support, genetic algorithm optimization, and modern React frontend.

## Features

- **Multi-Tenant Architecture**: Master admin can manage multiple colleges, each with their own dashboard
- **Genetic Algorithm**: Optimized timetable generation with constraint handling
- **Role-Based Access Control**: Master Admin, College Admin, HOD, Faculty, and Student roles
- **Modern Frontend**: React with TypeScript, Tailwind CSS, and responsive design
- **RESTful API**: Django REST Framework with JWT authentication
- **Scalable Design**: PostgreSQL database, Celery for async tasks, Redis for caching

## Project Structure

```
Time-Table/
├── backend/                 # Django backend
│   ├── algorithm/          # Genetic algorithm implementation
│   ├── api/                # Authentication endpoints
│   ├── core/               # Core models, views, serializers
│   └── timetable_backend/  # Django settings
├── frontend/               # React frontend
│   └── src/
│       ├── pages/         # Page components
│       ├── components/    # Reusable components
│       ├── stores/        # State management
│       └── lib/           # Utilities
└── README.md
```

## Setup Instructions

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

5. **Set up database:**
   ```bash
   python manage.py makemigrations core
   python manage.py migrate
   ```

6. **Create superuser (Master Admin):**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run server:**
   ```bash
   python manage.py runserver
   ```

### Frontend Setup

1. **Navigate to frontend directory:**
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

## Usage

### Master Admin

1. Login with master admin credentials
2. Navigate to Colleges section to add/manage colleges
3. Each college gets a unique subdomain and dashboard
4. Manage users across all colleges

### College Admin

1. Login with college admin credentials
2. Set up departments, teachers, subjects, sections, and classrooms
3. Generate timetables using the genetic algorithm
4. View and manage generated timetables

## API Endpoints

### Authentication
- `POST /api/auth/register/` - Register new user
- `POST /api/auth/login/` - Login
- `GET /api/auth/me/` - Get current user
- `POST /api/auth/logout/` - Logout

### Colleges (Master Admin only)
- `GET /api/colleges/` - List colleges
- `POST /api/colleges/` - Create college
- `GET /api/colleges/{id}/` - Get college details
- `PATCH /api/colleges/{id}/` - Update college
- `DELETE /api/colleges/{id}/` - Delete college

### Timetables
- `GET /api/timetables/` - List timetables
- `POST /api/timetables/` - Create timetable
- `GET /api/timetables/{id}/` - Get timetable details
- `POST /api/generate-timetable/generate/` - Generate timetable using GA

## Algorithm

The genetic algorithm optimizes timetable generation by:

1. **Initialization**: Creates random timetable populations
2. **Fitness Evaluation**: Scores timetables based on constraint violations
3. **Selection**: Selects best timetables for reproduction
4. **Crossover**: Combines features from parent timetables
5. **Mutation**: Introduces random changes for diversity
6. **Iteration**: Repeats for specified generations

### Constraints

- **Hard Constraints**: Must be satisfied
  - No teacher double-booking
  - No classroom double-booking
  - Room capacity limits
  - Teacher availability

- **Soft Constraints**: Preferences
  - Teacher time preferences
  - Balanced workload distribution
  - Minimize gaps between classes

## Sample Data

To add sample data for testing:

1. Use Django admin or API to create:
   - Colleges
   - Departments
   - Teachers
   - Subjects
   - Sections
   - Classrooms
   - Subject-Teacher mappings

2. Or use the management command (to be added):
   ```bash
   python manage.py load_sample_data
   ```

## Deployment

### Backend
- Use Gunicorn or uWSGI for production
- Set up PostgreSQL database
- Configure Redis for Celery
- Set environment variables securely

### Frontend
- Build for production: `npm run build`
- Serve static files with Nginx or similar
- Configure API proxy

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License
