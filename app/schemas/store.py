from pydantic import BaseModel, Field

class StoreConfigResponse(BaseModel):
    delivery_fee_cairo: str = Field(..., description="The authoritative delivery fee for Cairo in decimal format")
    is_store_accepting_orders: bool = Field(default=True, description="Whether the store is currently accepting new orders")
