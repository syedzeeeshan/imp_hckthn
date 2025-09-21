"""
Database router for Campus Club Management Suite
Routes models to appropriate databases (PostgreSQL or MongoDB)
"""

class DatabaseRouter:
    """
    A router to control all database operations on models
    """
    
    # PostgreSQL apps (relational data)
    postgres_apps = {
        'admin',
        'auth', 
        'contenttypes',
        'sessions',
        'messages',
        'staticfiles',
        'authtoken',
        'django_celery_beat',
        'authentication',
        'clubs',
        'events', 
        'analytics',
        'collaboration',
        'common',
    }
    
    # MongoDB apps (document-based data)
    mongodb_apps = {
        'notifications',
        'gamification', 
        'messaging',
    }
    
    def db_for_read(self, model, **hints):
        """Suggest the database to read from."""
        app_label = model._meta.app_label
        
        if app_label in self.postgres_apps:
            return 'default'
        elif app_label in self.mongodb_apps:
            return 'mongodb'
        return None

    def db_for_write(self, model, **hints):
        """Suggest the database to write to."""
        app_label = model._meta.app_label
        
        if app_label in self.postgres_apps:
            return 'default'
        elif app_label in self.mongodb_apps:
            return 'mongodb'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations if models are in the same app."""
        db_set = {'default', 'mongodb'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Ensure that certain apps' models get created on the right database."""
        if app_label in self.postgres_apps:
            return db == 'default'
        elif app_label in self.mongodb_apps:
            return db == 'mongodb'
        elif db in ['default', 'mongodb']:
            return False
        return None
