"""Password hashing and verification helpers."""

from passlib.context import CryptContext

# Create a password hashing utility to hash the password (user provided) into the database :)
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hash(password:str):
    """Hashes plaintext password using bcrypt and returns the hashed password 
    
    CryptContext manages password hashing algorithms and allows:
    - Hashing passwords
    - Verifying passwords
    - Upgrading hashing algorithms later
    """
    return pwd_context.hash(password)


def verify(password:str, hashed_password:str):
    """Function verifies if the user input password matches hashed password in db"""
    return pwd_context.verify(password,hashed_password)
