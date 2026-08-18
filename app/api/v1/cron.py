from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
import logging

from app.api.deps import get_db
from app.crud.crud_admin_auth import clean_expired_challenges
from app.core.config import settings
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/cleanup")
def run_cleanup(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Vercel Cron endpoint to clean up expired auth challenges.
    Should be called periodically (e.g., daily).
    """
    # Verify Vercel Cron Secret if configured
    if settings.CRON_SECRET:
        if not authorization or authorization != f"Bearer {settings.CRON_SECRET}":
            logger.warning("Unauthorized attempt to trigger cron cleanup.")
            raise HTTPException(status_code=401, detail="Unauthorized")
            
    try:
        clean_expired_challenges(db)
        logger.info("Cron: Successfully cleaned up expired admin auth challenges")
        return {"status": "success", "message": "Cleanup complete"}
    except Exception as e:
        logger.error(f"Cron: Failed to clean expired challenges: {e}")
        raise HTTPException(status_code=500, detail="Cleanup failed")
