"""
Testing settings for pytest and CI/CD
"""

from .base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'test-secret-key-for-testing-only'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': env.db('DATABASE_URL', default='postgres://test:test@localhost:5432/mettai_test')
}


# Password Hashing
# Use faster password hasher for tests
# https://docs.djangoproject.com/en/5.1/topics/testing/overview/#password-hashing

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]


# Disable migrations for faster tests
# https://docs.djangoproject.com/en/5.1/ref/django-admin/#cmdoption-migrate-run-syncdb

class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
