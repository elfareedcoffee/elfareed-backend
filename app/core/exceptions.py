from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

# Very basic dictionary for translating error codes
# In a real app, this might be loaded from JSON/YAML
ERROR_MESSAGES = {
    "INTERNAL_SERVER_ERROR": {"ar": "خطأ داخلي في الخادم", "en": "Internal server error"},
    "VALIDATION_ERROR": {"ar": "خطأ في التحقق من البيانات", "en": "Validation error"},
    "NOT_FOUND": {"ar": "غير موجود", "en": "Not found"},
    "UNAUTHORIZED": {"ar": "غير مصرح", "en": "Unauthorized"},
    "FORBIDDEN": {"ar": "مرفوض", "en": "Forbidden"},
    "PRODUCT_NOT_FOUND": {"ar": "المنتج غير موجود", "en": "Product not found"},
    "CATEGORY_NOT_FOUND": {"ar": "الفئة غير موجودة", "en": "Category not found"},
    "VARIANT_NOT_FOUND": {"ar": "الصنف غير موجود", "en": "Variant not found"},
    "CART_NOT_FOUND": {"ar": "سلة التسوق غير موجودة", "en": "Cart not found"},
    "ORDER_NOT_FOUND": {"ar": "الطلب غير موجود", "en": "Order not found"},
    "INSUFFICIENT_STOCK": {"ar": "الكمية غير كافية", "en": "Insufficient stock"},
    "INACTIVE_PRODUCT": {"ar": "المنتج غير مفعل", "en": "Product is not active"},
    "INACTIVE_VARIANT": {"ar": "الصنف غير مفعل", "en": "Variant is inactive"},
    "EMPTY_CART": {"ar": "سلة التسوق فارغة", "en": "Cart is empty"},
    "CART_EXPIRED": {"ar": "انتهت صلاحية سلة التسوق", "en": "Cart has expired"},
}

class APIException(Exception):
    def __init__(self, code: str, status_code: int = 400, message: str = None):
        self.code = code
        self.status_code = status_code
        self.message = message

def get_error_message(code: str, lang: str, fallback: str = None) -> str:
    if code in ERROR_MESSAGES:
        return ERROR_MESSAGES[code].get(lang, ERROR_MESSAGES[code].get("ar", fallback or code))
    return fallback or code

def get_request_lang(request: Request) -> str:
    accept_language = request.headers.get("accept-language", "")
    if "en" in accept_language.lower():
        return "en"
    return "ar" # Default

def add_exception_handlers(app: FastAPI):
    @app.exception_handler(APIException)
    async def api_error_handler(request: Request, exc: APIException):
        lang = get_request_lang(request)
        msg = exc.message or get_error_message(exc.code, lang)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": msg
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        lang = get_request_lang(request)
        
        # Map common HTTP status codes
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 401:
            code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            code = "FORBIDDEN"

        msg = get_error_message(code, lang, fallback=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": msg
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        lang = get_request_lang(request)
        msg = get_error_message("VALIDATION_ERROR", lang)
        
        # Pydantic errors leak internal field info occasionally, we map them purely for structure
        clean_errors = []
        for e in exc.errors():
            clean_errors.append({
                "loc": e.get("loc", []),
                "msg": e.get("msg", ""),
                "type": e.get("type", "")
            })
            
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": msg,
                    "details": clean_errors
                }
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        lang = get_request_lang(request)
        msg = get_error_message("INTERNAL_SERVER_ERROR", lang)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": msg
                }
            },
        )
