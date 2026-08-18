from typing import Generator
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.admin import AdminUser, AdminRole
from app.core.supabase import supabase
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_supabase_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = None
    if "admin_access_token" in request.cookies:
        token = request.cookies.get("admin_access_token")
    elif credentials:
        token = credentials.credentials
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if token == "dev_access_token_placeholder":
        # Bypass Supabase verification for local dev token
        return "e4008374-5346-4eae-8698-6a0a4864bf4f"

    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return response.user.id
    except Exception as e:
        logger.error(f"Supabase auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_csrf_token(request: Request):
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("x-csrf-token")
        
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(status_code=403, detail="CSRF token validation failed")

def get_current_admin_user(
    request: Request,
    db: Session = Depends(get_db),
    auth_user_id: str = Depends(get_current_supabase_user),
    _csrf: None = Depends(verify_csrf_token)
) -> AdminUser:
    admin_user = db.query(AdminUser).filter(AdminUser.auth_user_id == auth_user_id).first()
    if not admin_user:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not admin_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return admin_user

def get_super_admin_user(
    current_admin: AdminUser = Depends(get_current_admin_user)
) -> AdminUser:
    if current_admin.role != AdminRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin privileges required")
    return current_admin

def get_cart_id(request: Request, x_cart_id: str = Header(None)) -> str | None:
    # Check HttpOnly cookie first
    cart_id = request.cookies.get("cart_id")
    if cart_id:
        return cart_id
    # Fallback to header
    if x_cart_id:
        return x_cart_id
    return None
