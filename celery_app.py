import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# This is not a Django project, so we don't need this line.
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

# It's good practice to make broker and backend URLs configurable via environment variables.
CELERY_BROKER_URL_DEFAULT = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND_URL_DEFAULT = 'redis://localhost:6379/0' # Using Redis for results too

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', CELERY_BROKER_URL_DEFAULT)
CELERY_RESULT_BACKEND_URL = os.environ.get('CELERY_RESULT_BACKEND_URL', CELERY_RESULT_BACKEND_URL_DEFAULT)

# Initialize Celery
# The first argument is the name of the current module, for auto-generating names.
# We can use a more generic name like 'tasks_app' or the project name.
app = Celery('proj_celery_app', # Renamed from 'project' to avoid conflict with 'project' package
             broker=CELERY_BROKER_URL,
             backend=CELERY_RESULT_BACKEND_URL,
             include=['project.tasks']) # List of modules to import when celery worker starts.
                                        # 'project.tasks' is where we will define our tasks.

# Optional configuration, see the Celery documentation for more details.
app.conf.update(
    result_expires=3600, # Time (in seconds) for results to be stored.
    # task_serializer='json', # Default is json
    # accept_content=['json'],  # Default
    # result_serializer='json', # Default
    # timezone='UTC', # Example timezone
    # Configuration for better Windows compatibility
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,  # Process one task at a time to avoid memory issues
    task_acks_late=True,  # Acknowledge tasks only after completion
    # enable_utc=True, # Example
)

# This helps Celery autodiscover tasks in the modules listed in `include`.
# It assumes that tasks are defined using the @app.task decorator.
# For Celery 4.0+, autodiscover_tasks is often not needed if `include` is used correctly
# and tasks are defined in modules that Celery can import.
# However, explicitly calling it can be clearer or help in some structures.
# app.autodiscover_tasks(['project']) # This would search for 'tasks.py' in all apps under 'project'
# Since we specified 'project.tasks' in `include`, tasks should be found there.

if __name__ == '__main__':
    # This script can be used to start a worker, but typically you'd use the celery CLI.
    # Example: celery -A celery_app.app worker -l info
    print("Celery app configured. To start a worker, run:")
    print("celery -A celery_app.app worker -l info -P gevent # For gevent compatibility if tasks use it")
    # Adding -P gevent if your tasks might interact with gevent-based things like Flask-Sockets context,
    # though tasks are usually independent processes. For CPU-bound tasks like Whisper, default prefork pool is often fine.

    # To test configuration, you can try to send a task if one is defined and worker is running.
    # e.g. from project.tasks import some_task
    #      some_task.delay()
