from functools import wraps
from flask import request, g, jsonify
from firebase_admin import auth

def token_required(f):
    """
    Verifies the Firebase ID token in the Authorization header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                # Expected format: "Bearer <token>"
                token = request.headers.get('Authorization').split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Invalid Authorization header format. Expected "Bearer <token>"'}), 401

        if not token:
            return jsonify({'error': 'Authorization token is missing'}), 401

        try:
            # Verify the token
            decoded_token = auth.verify_id_token(token)
            # Store the decoded token in Flask's application context g
            g.current_user = decoded_token
            # You can also fetch your own user profile from your database here
            # g.user_profile = get_user_from_db(decoded_token['uid'])
            
        except auth.ExpiredIdTokenError:
            return jsonify({'error': 'Token has expired'}), 401
        except auth.InvalidIdTokenError as e:
            return jsonify({'error': 'Invalid token', 'details': str(e)}), 401
        except Exception as e:
            return jsonify({'error': 'An unexpected error occurred during token verification', 'details': str(e)}), 500

        return f(*args, **kwargs)

    return decorated_function
