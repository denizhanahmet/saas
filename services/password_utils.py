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
