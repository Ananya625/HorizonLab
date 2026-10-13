from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from app.auth import (
    USERS_DB,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: Dict[str, Any]

class UserProfileResponse(BaseModel):
    username: str
    email: str
    is_active: bool = True

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(req: RegisterRequest):
    """Registers a new user and returns JWT token."""
    if req.username in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_pwd = hash_password(req.password)
    user_record = {
        "username": req.username,
        "email": req.email,
        "hashed_password": hashed_pwd,
        "is_active": True
    }
    USERS_DB[req.username] = user_record

    access_token = create_access_token(data={"sub": req.username, "email": req.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"username": req.username, "email": req.email}
    }

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Authenticates user credentials and returns JWT bearer access token."""
    user = USERS_DB.get(req.username)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(data={"sub": user["username"], "email": user["email"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"username": user["username"], "email": user["email"]}
    }

@router.get("/me", response_model=UserProfileResponse)
def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Protected endpoint returning authenticated user profile."""
    return current_user
