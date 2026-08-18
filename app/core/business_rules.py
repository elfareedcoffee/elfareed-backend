from decimal import Decimal

def calculate_delivery_fee() -> Decimal:
    """
    Returns the current active delivery fee.
    Can be expanded later to check distance, governorate, or configurations.
    """
    return Decimal("50.00")
