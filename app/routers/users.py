"""This file handles the routing for users, such as creating users, and getting a specific user with an ID"""
from fastapi import APIRouter, Depends, HTTPException, status, Response
import models 
import database 
from schemas import user_schemas
from security import password, oauth2
from sqlalchemy.orm import Session 
from database import get_db


router = APIRouter(prefix="/users", tags=["users"])


# Create a user 
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=user_schemas.UserResponse)
async def create_user(user:user_schemas.UserCreate, db:Session = Depends(get_db)):
    """Function creates a user account while also using the password file to hash the password"""
    curr_user = db.query(models.User).filter(models.User.email == user.email).first()
    
    # if the user already exists do not log the user in
    if curr_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"EMAIL ALREADY EXISTS")
    # Otherwise hash the password
    hashed_password = password.hash(user.password)
    user.password = hashed_password 
    # update the db 
    new_user = models.User(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = oauth2.create_access_token(data={"user_id": new_user.id})
    return {
        "id": new_user.id,
        "email": new_user.email,
        "created_at": new_user.created_at,
        "access_token": access_token,
        "token_type": "bearer",
    }




# CURRENT USER (ACCOUNT) ENDPOINT LOGIC START----

@router.get("/me", response_model=user_schemas.UserResponse)
async def get_current_user_profile(curr_user:models.User = Depends(oauth2.get_current_user)):
    """Returns the profile of the user"""
    return curr_user

#Change the password
@router.put("/me/password", response_model=user_schemas.UserResponse)
async def change_password(payload:user_schemas.PasswordChange, db:Session=Depends(get_db), curr_user:models.User = Depends(oauth2.get_current_user)):
    """Function allows users to change their passwords """
    if not password.verify(payload.current_password, curr_user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current password is incorrect.",
        )

    if not payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be empty.",
        )
    curr_user.password = password.hash(payload.new_password)
    db.commit()
    db.refresh(curr_user)
    return curr_user


# Delete the account

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    db: Session = Depends(get_db),
    curr_user: models.User = Depends(oauth2.get_current_user),
):
    """Delete the logged-in user's account along with all their items (don't have that yet)"""
    db.delete(curr_user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
# CURRENT USER (ACCOUNT) ENDPOINT LOGIC END----


# Get specific user by id
@router.get("/{id}", response_model=user_schemas.UserResponse)
async def get_user(id:int, db:Session = Depends(get_db)):
    """route to get a specific user id :D"""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID: {id} not FOUND!")
    return user



