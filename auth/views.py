from flask import jsonify, request
from utilities.logger import setup_logger
from auth.init import auth_bp

# Initialize logger
logger = setup_logger('auth_logger', 'logs/auth.log')

@auth_bp.route('/login', methods=['POST'])
def login():
    logger.info('Login attempt')
    return jsonify({'message': 'Login successful'}), 200