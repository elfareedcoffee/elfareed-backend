from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.db.models.admin import AdminUser, AdminAuthChallenge, AdminPhoneChangeChallenge
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import json
from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_fernet() -> Fernet:
    if not settings.SESSION_ENCRYPTION_KEY:
        raise ValueError("SESSION_ENCRYPTION_KEY is not set in the environment.")
    return Fernet(settings.SESSION_ENCRYPTION_KEY.encode())

def encrypt_session_data(data: dict) -> str:
    f = get_fernet()
    json_data = json.dumps(data).encode("utf-8")
    return f.encrypt(json_data).decode("utf-8")

def decrypt_session_data(encrypted_str: str) -> dict:
    f = get_fernet()
    decrypted_data = f.decrypt(encrypted_str.encode("utf-8"))
    return json.loads(decrypted_data.decode("utf-8"))

def generate_otp() -> str:
    # 6-digit cryptographically random OTP
    return "".join(secrets.choice("0123456789") for _ in range(6))

def hash_otp(otp: str) -> str:
    return pwd_context.hash(otp)

def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    return pwd_context.verify(plain_otp, hashed_otp)

def invalidate_existing_challenges(db: Session, admin_id: uuid.UUID):
    db.query(AdminAuthChallenge).filter(
        AdminAuthChallenge.admin_user_id == admin_id,
        AdminAuthChallenge.consumed_at == None,
        AdminAuthChallenge.expires_at > datetime.now(timezone.utc)
    ).update({"consumed_at": datetime.now(timezone.utc), "encrypted_session": None})
    db.commit()

def create_challenge(db: Session, admin_id: uuid.UUID, session_data: dict) -> tuple[AdminAuthChallenge, str]:
    # Invalidate old challenges
    invalidate_existing_challenges(db, admin_id)
    
    otp = generate_otp()
    hashed = hash_otp(otp)
    
    encrypted_session = encrypt_session_data(session_data)
    
    challenge = AdminAuthChallenge(
        admin_user_id=admin_id,
        code_hash=hashed,
        encrypted_session=encrypted_session,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge, otp

def get_challenge_for_update(db: Session, challenge_id: uuid.UUID) -> AdminAuthChallenge | None:
    # Use with_for_update to lock the row and prevent race conditions
    try:
        return db.query(AdminAuthChallenge).filter(AdminAuthChallenge.id == challenge_id).with_for_update(nowait=True).first()
    except OperationalError:
        # If the row is locked by another transaction and nowait=True throws, it means concurrent request
        return None

def clean_expired_challenges(db: Session):
    db.query(AdminAuthChallenge).filter(
        AdminAuthChallenge.expires_at <= datetime.now(timezone.utc),
        AdminAuthChallenge.encrypted_session != None
    ).update({"encrypted_session": None})
    db.commit()

def invalidate_existing_phone_change_challenges(db: Session, admin_id: uuid.UUID):
    db.query(AdminPhoneChangeChallenge).filter(
        AdminPhoneChangeChallenge.admin_user_id == admin_id,
        AdminPhoneChangeChallenge.consumed_at == None,
        AdminPhoneChangeChallenge.expires_at > datetime.now(timezone.utc)
    ).update({"consumed_at": datetime.now(timezone.utc)})
    db.commit()

def create_phone_change_challenge(db: Session, admin_id: uuid.UUID, new_phone_number: str) -> tuple[AdminPhoneChangeChallenge, str]:
    # Invalidate old phone change challenges
    invalidate_existing_phone_change_challenges(db, admin_id)
    
    otp = generate_otp()
    hashed = hash_otp(otp)
    
    challenge = AdminPhoneChangeChallenge(
        admin_user_id=admin_id,
        new_phone_number=new_phone_number,
        code_hash=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge, otp

def get_phone_change_challenge_for_update(db: Session, challenge_id: uuid.UUID) -> AdminPhoneChangeChallenge | None:
    # Use with_for_update to lock the row and prevent race conditions
    try:
        return db.query(AdminPhoneChangeChallenge).filter(AdminPhoneChangeChallenge.id == challenge_id).with_for_update(nowait=True).first()
    except OperationalError:
        return None
