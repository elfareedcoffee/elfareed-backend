from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_db, get_cart_id
from app.crud import crud_order
from app.core.exceptions import APIException
from app.core.limiter import limiter
from app.schemas.order import OrderCreate, OrderCheckoutResponse, OrderResponse, OrderRecoverRequest
from app.db.models.order import Order

router = APIRouter()

@router.post("/", response_model=OrderCheckoutResponse)
@limiter.limit("5/minute")
def checkout(
    request: Request,
    order_in: OrderCreate,
    response: Response,
    cart_id: str | None = Depends(get_cart_id),
    db: Session = Depends(get_db)
):
    if not cart_id:
        raise APIException(status_code=400, code="CART_NOT_FOUND")
        
    order = crud_order.create_order_from_cart(db, cart_id, order_in)
    
    # Delete the cookie so the frontend knows the cart is gone
    response.delete_cookie("cart_id")
    
    return order

@router.get("/track/{tracking_token}", response_model=OrderResponse)
@limiter.limit("10/minute")
def track_order(
    request: Request,
    tracking_token: UUID,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.tracking_token == tracking_token).first()
    if not order:
        raise APIException(status_code=404, code="ORDER_NOT_FOUND")
    return order

@router.post("/recover", response_model=OrderCheckoutResponse)
@limiter.limit("5/minute")
def recover_order(
    request: Request,
    req: OrderRecoverRequest,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.order_number == req.order_number,
        Order.customer_phone == req.customer_phone
    ).first()
    
    if not order:
        raise APIException(status_code=404, code="ORDER_NOT_FOUND")
        
    return order
