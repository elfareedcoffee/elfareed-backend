from fastapi import APIRouter
from app.core.limiter import limiter
from app.core.business_rules import calculate_delivery_fee
from app.schemas.store import StoreConfigResponse
from fastapi import Request

router = APIRouter()

@router.get("/config", response_model=StoreConfigResponse)
@limiter.limit("20/minute")
def get_store_config(request: Request):
    """
    Public endpoint to retrieve non-sensitive store configuration.
    The delivery fee is dynamically calculated using the backend's authoritative business rule.
    """
    delivery_fee = calculate_delivery_fee()
    
    return StoreConfigResponse(
        delivery_fee_cairo=str(delivery_fee),
        is_store_accepting_orders=True
    )
