---
description: Create a new Django project with best practices and modern structure
---

You are creating a new Django project following current best practices (2025).

## Project Configuration

Ask the user these questions:

1. **Project name** (e.g., "myproject")
2. **Python version** (recommend 3.12+)
3. **Database**: PostgreSQL (recommended), MySQL, or SQLite
4. **Optional features**:
   - Django REST Framework (API development)
   - Celery (background tasks)
   - Redis (caching/sessions)
   - Docker setup
   - GitHub Actions CI/CD

## Project Structure

Create a modern Django project with this structure:

```
{project_name}/
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py      # Shared settings
│   │   ├── local.py     # Development
│   │   └── production.py # Production
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   └── __init__.py
├── requirements/
│   ├── base.txt         # Core dependencies
│   ├── local.txt        # Dev dependencies
│   └── production.txt   # Production dependencies
├── static/
├── media/
├── templates/
├── .env.example
├── .gitignore
├── manage.py
├── README.md
└── pytest.ini
```

## Implementation Steps

1. **Create virtual environment**:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   ```

2. **Install Django**:
   ```bash
   pip install django
   ```

3. **Create project**:
   ```bash
   django-admin startproject config .
   ```

4. **Reorganize for split settings**:
   - Move `settings.py` → `settings/base.py`
   - Create `settings/local.py` and `settings/production.py`
   - Update imports

5. **Create apps directory**:
   ```bash
   mkdir apps
   touch apps/__init__.py
   ```

6. **Setup requirements files**:

   **requirements/base.txt**:
   ```
   Django>=5.0,<5.1
   python-decouple>=3.8
   psycopg2-binary>=2.9  # If PostgreSQL
   ```

   **requirements/local.txt**:
   ```
   -r base.txt
   django-debug-toolbar>=4.2
   pytest-django>=4.7
   black>=24.0
   ruff>=0.1
   ```

   **requirements/production.txt**:
   ```
   -r base.txt
   gunicorn>=21.0
   whitenoise>=6.6
   ```

7. **Create .env.example**:
   ```
   DEBUG=True
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

8. **Setup .gitignore**:
   ```
   *.pyc
   __pycache__/
   venv/
   .env
   db.sqlite3
   media/
   staticfiles/
   .pytest_cache/
   ```

9. **Configure settings/base.py**:
   - Import decouple for environment variables
   - Set up apps directory path
   - Configure static/media settings
   - Add security settings

10. **Create README.md** with setup instructions

11. **Initialize git**:
    ```bash
    git init
    git add .
    git commit -m "Initial Django project setup"
    ```

## If Django REST Framework selected

Add to requirements/base.txt:
```
djangorestframework>=3.14
django-cors-headers>=4.3
django-filter>=23.5
```

Configure in settings/base.py:
- Add to INSTALLED_APPS
- Configure REST_FRAMEWORK settings
- Add CORS settings

## If Celery selected

Add to requirements/base.txt:
```
celery>=5.3
redis>=5.0
django-celery-beat>=2.5
```

Create:
- `config/celery.py`
- `config/__init__.py` with Celery app import

## If Docker selected

Create:
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

## Post-Setup Tasks

1. Create first migration:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

3. Run development server to verify:
   ```bash
   python manage.py runserver
   ```

## Best Practices Applied

✓ Split settings for different environments
✓ Apps organized in dedicated directory
✓ Environment variables for sensitive data
✓ Modern dependency management
✓ Git-ready with proper .gitignore
✓ Testing setup included
✓ Code quality tools (Black, Ruff)

After completing the setup, offer to run `/django:worktree-setup` if the user wants to configure git worktrees for dev/staging/production workflows.
