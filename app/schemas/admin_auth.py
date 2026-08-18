from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    requires_verification: bool
    verification_id: str

class AdminVerifyRequest(BaseModel):
    verification_id: str
    code: str

class AdminSuccessResponse(BaseModel):
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    csrf_token: Optional[str] = None

class AdminMeResponse(BaseModel):
    id: str
    username: str
    name: str
    role: str
    email: str
    phone_number: str
    is_active: bool
    created_at: datetime

class AdminProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)

class AdminPhoneChangeRequest(BaseModel):
    new_phone_number: str = Field(..., min_length=10, max_length=20)

class AdminPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
