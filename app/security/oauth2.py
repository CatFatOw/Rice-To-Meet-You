"""OAuth2/JWT helpers for creating tokens and loading the current user."""

from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone 
import os 
from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from schemas import auth_schemas
from database import get_db 
from sqlalchemy.orm import Session
import models


# Tell fastapi where clients can obtain tokens/make tokens available 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "/login")
SECRET_KEY = os.getenv("JWT_KEY")
ALGORITHM = "HS256"
# Token expiration time (80 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 80

def create_access_token(data:dict):
    """Function creates the JWT authentication token"""
    if not SECRET_KEY:
        raise RuntimeError("JWT_KEY not provided")
    
    to_encode = data.copy()
    # Create expiration time for when key expires 
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # update the dictionary w/ expiration time 
    to_encode.update({"exp":expire})
    # encode the data via jwt 
    return jwt.encode(to_encode, SECRET_KEY, ALGORITHM)


def verify_access_token(token:str, credentials_exception):
    """Function validates if the JWT token is still valid"""
    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHM)
        # If the user_id is fed via the auth route
        id = payload.get("user_id")
        if not id:
            raise credentials_exception
        token_data = auth_schemas.TokenData(id=id)
    # token not valid 
    except JWTError:
        raise credentials_exception
    return token_data


def get_current_user(token:str = Depends(oauth2_scheme), db:Session = Depends(get_db)):
    """Function makes fastapi look for authorization heade,r extracts the bearer and passes 
    the token string into a token"""
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"COULD NOT VALIDATE YOUR CREDENTIAL",
                                         headers={"WWW-Authenticate": "Bearer"})
    token = verify_access_token(token, credential_exception)
    user = db.query(models.User).filter(models.User.id == token.id).first()
    return user 
