import hashlib
import os


def hash_password(password: str, iterations: int = 600_000) -> str:
    """CPU work done in C (OpenSSL), not in Python bytecode."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"