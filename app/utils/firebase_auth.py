import os
import requests
from flask import current_app

DEFAULT_FIREBASE_API_KEY = "AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg"

def normalize_email(email: str) -> str:
    """Normalize email by trimming whitespace and converting to lowercase."""
    if not email:
        return ""
    return email.strip().lower()

def verify_google_id_token(id_token: str) -> dict:
    """
    Cryptographically verify a Firebase ID token issued for Google Sign-In.
    Extracts verified email, email_verified status, and Firebase UID.
    
    Returns:
        dict with keys:
            valid (bool): True if token is verified and active.
            email (str): Normalized verified email address.
            email_verified (bool): True if email is confirmed by Google/Firebase.
            uid (str): Firebase UID.
            error (str, optional): Description of failure if invalid.
    """
    if not id_token or not isinstance(id_token, str) or not id_token.strip():
        return {
            'valid': False,
            'error': 'Missing or empty Firebase ID token.'
        }

    id_token = id_token.strip()

    # 1. Attempt verification with firebase_admin if initialized
    try:
        import firebase_admin
        from firebase_admin import auth as fb_auth
        if firebase_admin._apps:
            decoded = fb_auth.verify_id_token(id_token)
            email = normalize_email(decoded.get('email', ''))
            email_verified = decoded.get('email_verified', False)
            uid = decoded.get('uid', '')
            return {
                'valid': True,
                'email': email,
                'email_verified': email_verified,
                'uid': uid,
                'raw': decoded
            }
    except Exception as e:
        # If firebase_admin is not initialized with credentials or fails, fallback to Identity Toolkit
        if current_app:
            current_app.logger.debug(f"firebase_admin verification fallback: {e}")

    # 2. Verify via Google Identity Toolkit accounts:lookup API
    try:
        api_key = os.environ.get('FIREBASE_API_KEY', DEFAULT_FIREBASE_API_KEY)
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
        resp = requests.post(verify_url, json={'idToken': id_token}, timeout=7)
        
        if resp.status_code == 200:
            data = resp.json()
            users = data.get('users', [])
            if not users:
                return {
                    'valid': False,
                    'error': 'User profile not found in Firebase token response.'
                }
            user_info = users[0]
            email = normalize_email(user_info.get('email', ''))
            email_verified = user_info.get('emailVerified', False)
            uid = user_info.get('localId', '')

            # Google Sign-In emails are automatically verified by Google
            provider_list = [p.get('providerId') for p in user_info.get('providerUserInfo', [])]
            if 'google.com' in provider_list:
                email_verified = True

            if not email:
                return {
                    'valid': False,
                    'error': 'Google account did not provide an email address.'
                }

            return {
                'valid': True,
                'email': email,
                'email_verified': email_verified,
                'uid': uid,
                'raw': user_info
            }
        else:
            err_data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
            err_msg = err_data.get('error', {}).get('message', f'HTTP {resp.status_code}')
            return {
                'valid': False,
                'error': f"Firebase token verification failed: {err_msg}"
            }
    except requests.RequestException as req_err:
        if current_app:
            current_app.logger.error(f"Network error during Firebase token verification: {req_err}")
        return {
            'valid': False,
            'error': f"Network error connecting to Google Identity verification: {str(req_err)}"
        }
    except Exception as ex:
        if current_app:
            current_app.logger.error(f"Unexpected error verifying Firebase token: {ex}")
        return {
            'valid': False,
            'error': f"Authentication token verification error: {str(ex)}"
        }
