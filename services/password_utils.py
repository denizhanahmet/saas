import os
import hashlib
import secrets

PBKDF2_ITERATIONS = 100_000
PBKDF2_ALGORITHM = 'sha256'
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32

def hash_password_pbkdf2(password: str) -> dict:
    """
    Returns a dict with 'hash', 'salt', and 'iterations' for the given password.
    """
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    hash_bytes = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode(),
        salt,
        PBKDF2_ITERATIONS,
        PBKDF2_HASH_BYTES
    )
    return {
        'hash': hash_bytes.hex(),
        'salt': salt.hex(),
        'iterations': PBKDF2_ITERATIONS
    }

def verify_password_pbkdf2(password: str, hash_hex: str, salt_hex: str, iterations: int) -> bool:
    salt = bytes.fromhex(salt_hex)
    hash_bytes = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode(),
        salt,
        iterations,
        PBKDF2_HASH_BYTES
    )
    return hash_bytes.hex() == hash_hex


def generate_temp_password(length: int = 12) -> str:
    """
    Generate a cryptographically secure temporary password.
    Ensures at least 1 uppercase, 1 lowercase, 1 digit, 1 special character.
    
    Args:
        length: Password length (minimum 8, default 12)
    
    Returns:
        A secure random password string
    """
    if length < 8:
        length = 8
    
    import string
    
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"
    all_chars = uppercase + lowercase + digits + special
    
    # Ensure at least one of each required character type
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill remaining length with random characters
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    
    # Shuffle to avoid predictable positions
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    
    return ''.join(password_list)
