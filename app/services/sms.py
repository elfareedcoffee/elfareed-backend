import logging
from typing import Optional
from abc import ABC, abstractmethod
from app.core.config import settings

logger = logging.getLogger(__name__)

class SMSProviderException(Exception):
    pass

class SMSProvider(ABC):
    @abstractmethod
    def send_otp(self, to_phone: str, code: str) -> None:
        pass

class MockSMSProvider(SMSProvider):
    def send_otp(self, to_phone: str, code: str) -> None:
        if settings.ENVIRONMENT == "production":
            raise SMSProviderException("Mock SMS provider cannot be used in production.")
        # In non-production, we log the code so devs can use it
        logger.info(f"MOCK SMS: Would have sent OTP to {to_phone}. Code is {code}")
        print(f"\n======================================")
        print(f"🔒 DEV MOCK OTP FOR {to_phone}: {code}")
        print(f"======================================\n")

class ExternalSMSProvider(SMSProvider):
    def __init__(self, provider: str, api_key: str, api_secret: str, sender: str):
        self.provider = provider
        self.api_key = api_key
        self.api_secret = api_secret
        self.sender = sender

    def send_otp(self, to_phone: str, code: str) -> None:
        # Here we would use the actual provider SDK (Twilio, Vonage, etc.)
        # For now, it fails if it's not fully implemented
        raise SMSProviderException(f"External SMS provider '{self.provider}' is not yet implemented.")

def get_sms_provider() -> SMSProvider:
    if not settings.SMS_ENABLED:
        if settings.ENVIRONMENT == "production":
            raise SMSProviderException("SMS must be enabled in production.")
        return MockSMSProvider()

    if not settings.SMS_PROVIDER or settings.SMS_PROVIDER.lower() == "mock":
        if settings.ENVIRONMENT == "production":
            raise SMSProviderException("A real SMS provider must be configured in production.")
        return MockSMSProvider()
        
    if not settings.SMS_API_KEY:
        if settings.ENVIRONMENT == "production":
            raise SMSProviderException("SMS_API_KEY is missing in production.")
        return MockSMSProvider()

    return ExternalSMSProvider(
        provider=settings.SMS_PROVIDER,
        api_key=settings.SMS_API_KEY,
        api_secret=settings.SMS_API_SECRET or "",
        sender=settings.SMS_SENDER or ""
    )

sms_service = get_sms_provider()
