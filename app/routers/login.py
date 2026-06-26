"""Route handles the logic for user, jwt authentication and login endpoints"""
from fastapi import HTTPException, APIRouter, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session 
import models
from database import get_db
from security import oauth2
from schemas import auth_schemas
from security.password import verify

router = APIRouter(prefix="/login", tags=["auth"])

# get the user (follow the schema)
@router.post("/", response_model=auth_schemas.Token)
async def login(user_credentials:OAuth2PasswordRequestForm=Depends(), db:Session=Depends(get_db)):
    """Route used to get user credentials and login user"""
    user = db.query(models.User).filter(models.User.email == user_credentials.username).first()

    # if the user doesn't exist 
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"INVALID CREDENTIALS")
    # Missed password
    if not verify(user_credentials.password, user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"INVALID CREDENTIALS")
    
    # Otherwise, user is valid 
    access_token = oauth2.create_access_token(data={"user_id":user.id})
    return {"access_token":access_token, "token_type":"bearer"}
