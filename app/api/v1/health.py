from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "ok", "message": "Backend is running"}

@router.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    try:
        # Perform a simple, non-blocking DB query
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready"
        )
