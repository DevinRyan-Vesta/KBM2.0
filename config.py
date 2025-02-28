import os

class Config:
    DEBUG = False
    TESTING = False
    DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///:memory:')

class ProductionConfig(Config):
    DATABASE_URI = os.getenv('DATABASE_URI', 'mysql://user@localhost/foo')

class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///development.db')

class TestingConfig(Config):
    TESTING = True
    DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///testing.db')

def get_config(env):
    if env == 'production':
        return ProductionConfig()
    elif env == 'development':
        return DevelopmentConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return Config()

# Example usage:
# config = get_config(os.getenv('ENV', 'development'))