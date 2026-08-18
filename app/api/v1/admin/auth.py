from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
import logging
import secrets
from app.core.config import settings

from app.api.deps import get_db, get_current_admin_user
from app.crud.crud_admin_auth import (
    create_challenge,
    get_challenge_for_update,
    verify_otp,
    decrypt_session_data,
    clean_expired_challenges,
    create_phone_change_challenge,
    get_phone_change_challenge_for_update
)
from app.schemas.admin_auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminVerifyRequest,
    AdminSuccessResponse,
    AdminMeResponse,
    AdminProfileUpdateRequest,
    AdminPhoneChangeRequest,
    AdminPasswordChangeRequest
)
from app.db.models.admin import AdminUser
from app.core.supabase import supabase, supabase_admin
from app.services.sms import sms_service, SMSProviderException
from app.core.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Uniform generic error response to prevent enumeration
def raise_unauthorized():
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/login", response_model=AdminSuccessResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    login_data: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    # Strip whitespace and lowercase username for resilience against mobile keyboards
    username = login_data.username.strip().lower()
    password = login_data.password.strip()

    # 1. Look up admin user by username
    admin_user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin_user or not admin_user.is_active:
        raise_unauthorized()

    # 2. Authenticate via Supabase Auth
    if "your-project.supabase.co" in settings.SUPABASE_URL:
        # Development Bypass
        if password not in ["El2@26@Fareed\\", "admin"]:
            raise_unauthorized()
        access_token = "dev_access_token_placeholder"
        refresh_token = "dev_refresh_token_placeholder"
    else:
        try:
            auth_res = supabase.auth.sign_in_with_password({
                "email": admin_user.email,
                "password": login_data.password
            })
            if not auth_res.user:
                raise_unauthorized()
                
            access_token = auth_res.session.access_token
            refresh_token = auth_res.session.refresh_token
        except Exception as e:
            logger.warning("Supabase auth failure during admin login")
            raise_unauthorized()

    # 3. Set cookies directly (bypassing OTP)
    is_prod = settings.ENVIRONMENT == "production"
    
    response.set_cookie(
        key="admin_access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=3600
    )
    response.set_cookie(
        key="admin_refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=30 * 24 * 3600
    )
    
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_prod,
        samesite="lax",
        max_age=3600
    )

    return AdminSuccessResponse(message="Logged in successfully")

@router.post("/verify", response_model=AdminSuccessResponse)
@limiter.limit("5/minute")
def verify(
    request: Request,
    response: Response,
    verify_data: AdminVerifyRequest,
    db: Session = Depends(get_db)
):
    try:
        verification_id = UUID(verify_data.verification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid verification ID format")

    challenge = get_challenge_for_update(db, verification_id)
    
    if not challenge:
        # Prevent exposing that it's a locked row vs nonexistent challenge for security
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")

    if challenge.consumed_at:
        db.rollback() # Release lock
        raise HTTPException(status_code=400, detail="Challenge already consumed")
        
    if challenge.expires_at <= datetime.now(timezone.utc):
        challenge.encrypted_session = None # Explicit cleanup
        db.commit()
        raise HTTPException(status_code=400, detail="Challenge expired")
        
    if challenge.attempts >= challenge.max_attempts:
        challenge.encrypted_session = None
        db.commit()
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    # Verify OTP
    if not verify_otp(verify_data.code, challenge.code_hash):
        challenge.attempts += 1
        if challenge.attempts >= challenge.max_attempts:
            challenge.encrypted_session = None
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect verification code")

    # Success: decrypt session and consume challenge
    if not challenge.encrypted_session:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error: session missing")
        
    try:
        session_data = decrypt_session_data(challenge.encrypted_session)
    except Exception as e:
        logger.error("Failed to decrypt pending session")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error during session decryption")

    challenge.consumed_at = datetime.now(timezone.utc)
    challenge.encrypted_session = None # Explicit destruction of tokens in DB
    db.commit()

    is_prod = settings.ENVIRONMENT == "production"
    
    response.set_cookie(
        key="admin_access_token",
        value=session_data["access_token"],
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=3600 # 1 hour roughly
    )
    response.set_cookie(
        key="admin_refresh_token",
        value=session_data["refresh_token"],
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=30 * 24 * 3600 # 30 days
    )
    
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_prod,
        samesite="lax",
        max_age=3600
    )

    return AdminSuccessResponse(message="Verified successfully")

@router.get("/me", response_model=AdminMeResponse)
def get_me(admin_user: AdminUser = Depends(get_current_admin_user)):
    return AdminMeResponse(
        id=str(admin_user.id),
        username=admin_user.username,
        name=admin_user.name,
        role=admin_user.role.value,
        email=admin_user.email,
        phone_number=admin_user.phone_number,
        is_active=admin_user.is_active,
        created_at=admin_user.created_at
    )

@router.patch("/profile", response_model=AdminMeResponse)
def update_profile(
    profile_data: AdminProfileUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin_user)
):
    if profile_data.name is not None:
        admin_user.name = profile_data.name
    db.commit()
    db.refresh(admin_user)
    return get_me(admin_user)

@router.post("/security/phone/request", response_model=AdminLoginResponse)
@limiter.limit("5/minute")
def request_phone_change(
    request: Request,
    change_data: AdminPhoneChangeRequest,
    db: Session = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin_user)
):
    # Check if phone number is already used
    existing = db.query(AdminUser).filter(AdminUser.phone_number == change_data.new_phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number is already in use")

    challenge, otp = create_phone_change_challenge(db, admin_user.id, change_data.new_phone_number)

    try:
        sms_service.send_otp(to_phone=change_data.new_phone_number, code=otp)
    except SMSProviderException as e:
        logger.error(f"SMS Provider Error: {e}")
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to send SMS")
    except Exception as e:
        logger.error(f"Unexpected error sending SMS: {e}")
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to send SMS")

    return AdminLoginResponse(
        requires_verification=True,
        verification_id=str(challenge.id)
    )

@router.post("/security/phone/verify", response_model=AdminSuccessResponse)
@limiter.limit("5/minute")
def verify_phone_change(
    request: Request,
    verify_data: AdminVerifyRequest,
    db: Session = Depends(get_db),
    admin_user: AdminUser = Depends(get_current_admin_user)
):
    try:
        verification_id = UUID(verify_data.verification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid verification ID format")

    challenge = get_phone_change_challenge_for_update(db, verification_id)
    if not challenge or challenge.admin_user_id != admin_user.id:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")

    if challenge.consumed_at:
        db.rollback()
        raise HTTPException(status_code=400, detail="Challenge already consumed")
        
    if challenge.expires_at <= datetime.now(timezone.utc):
        db.rollback()
        raise HTTPException(status_code=400, detail="Challenge expired")
        
    if challenge.attempts >= challenge.max_attempts:
        db.rollback()
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    if not verify_otp(verify_data.code, challenge.code_hash):
        challenge.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect verification code")

    # Success: update phone number
    challenge.consumed_at = datetime.now(timezone.utc)
    admin_user.phone_number = challenge.new_phone_number
    db.commit()

    return AdminSuccessResponse(message="Phone number updated successfully")

@router.post("/security/password", response_model=AdminSuccessResponse)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    response: Response,
    password_data: AdminPasswordChangeRequest,
    admin_user: AdminUser = Depends(get_current_admin_user)
):
    # 1. Verify current password
    try:
        auth_res = supabase.auth.sign_in_with_password({
            "email": admin_user.email,
            "password": password_data.current_password
        })
        if not auth_res.user:
            raise HTTPException(status_code=400, detail="Incorrect current password")
    except Exception as e:
        logger.warning(f"Failed to verify current password for admin {admin_user.id}")
        raise HTTPException(status_code=400, detail="Incorrect current password")

    # 2. Update password
    try:
        res = supabase_admin.auth.admin.update_user_by_id(
            str(admin_user.auth_user_id),
            {"password": password_data.new_password}
        )
        if not res.user:
            raise HTTPException(status_code=500, detail="Failed to update password")
    except Exception as e:
        logger.error(f"Error updating password in Supabase: {e}")
        raise HTTPException(status_code=500, detail="Failed to update password")

    # 3. Invalidate current session cookies
    response.delete_cookie(key="admin_access_token", samesite="lax", secure=settings.ENVIRONMENT == "production")
    response.delete_cookie(key="admin_refresh_token", samesite="lax", secure=settings.ENVIRONMENT == "production")
    response.delete_cookie(key="csrf_token", samesite="lax", secure=settings.ENVIRONMENT == "production")

    return AdminSuccessResponse(message="Password changed successfully. Please log in again.")

@router.post("/logout", response_model=AdminSuccessResponse)
def logout(
    request: Request,
    response: Response,
    admin_user: AdminUser = Depends(get_current_admin_user)
):
    """
    Log out the current admin.
    Note: Supabase sign_out invalidates the refresh token server-side.
    The access token remains technically valid until its expiration time 
    (which is short-lived) due to JWT statelessness.
    The frontend must destroy its local tokens.
    """
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif "admin_access_token" in request.cookies:
        token = request.cookies.get("admin_access_token")

    if token:
        try:
            supabase.auth.set_session(access_token=token, refresh_token="")
            supabase.auth.sign_out()
        except Exception as e:
            logger.warning(f"Error during Supabase sign_out: {e}")
            
    response.delete_cookie(key="admin_access_token", samesite="lax", secure=settings.ENVIRONMENT == "production")
    response.delete_cookie(key="admin_refresh_token", samesite="lax", secure=settings.ENVIRONMENT == "production")
    response.delete_cookie(key="csrf_token", samesite="lax", secure=settings.ENVIRONMENT == "production")
            
    return AdminSuccessResponse(message="Logged out successfully")

@router.post("/refresh", response_model=AdminSuccessResponse)
@limiter.limit("10/minute")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    refresh_token = request.cookies.get("admin_refresh_token")
    if not refresh_token:
        raise_unauthorized()
    try:
        auth_res = supabase.auth.refresh_session(refresh_token)
        if not auth_res.user:
            raise_unauthorized()
            
        # Security requirement: check if the user is active in our DB
        # The Supabase ID is mapped to admin_user.auth_user_id
        admin_user = db.query(AdminUser).filter(AdminUser.auth_user_id == UUID(auth_res.user.id)).first()
        if not admin_user or not admin_user.is_active:
            raise_unauthorized()
            
        is_prod = settings.ENVIRONMENT == "production"
        response.set_cookie(
            key="admin_access_token",
            value=auth_res.session.access_token,
            httponly=True,
            secure=is_prod,
            samesite="lax",
            max_age=auth_res.session.expires_in
        )
        response.set_cookie(
            key="admin_refresh_token",
            value=auth_res.session.refresh_token,
            httponly=True,
            secure=is_prod,
            samesite="lax",
            max_age=30 * 24 * 3600
        )
        
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=is_prod,
            samesite="lax",
            max_age=auth_res.session.expires_in
        )
        return AdminSuccessResponse(message="Token refreshed successfully")
    except Exception as e:
        logger.warning(f"Supabase auth failure during admin refresh: {e}")
        raise_unauthorized()
