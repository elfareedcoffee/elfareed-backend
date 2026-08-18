import uuid
import os
import mimetypes
from urllib.parse import urlparse
from app.core.supabase import supabase_admin
import logging

logger = logging.getLogger(__name__)

BUCKET_NAME = "product-images"

def upload_product_image(file_bytes: bytes, mime_type: str) -> str:
    """
    Uploads a product image to Supabase storage.
    Returns the public URL of the uploaded image.
    """
    ext = mimetypes.guess_extension(mime_type)
    if not ext:
        # Fallback based on mime if guess fails
        if "jpeg" in mime_type or "jpg" in mime_type:
            ext = ".jpg"
        elif "png" in mime_type:
            ext = ".png"
        elif "webp" in mime_type:
            ext = ".webp"
        else:
            ext = ".bin"
            
    filename = f"{uuid.uuid4().hex}{ext}"
    
    try:
        supabase_admin.storage.from_(BUCKET_NAME).upload(
            file=file_bytes,
            path=filename,
            file_options={"content-type": mime_type}
        )
        
        # Get public url
        res = supabase_admin.storage.from_(BUCKET_NAME).get_public_url(filename)
        return res
    except Exception as e:
        logger.error(f"Error uploading image to Supabase Storage: {e}")
        raise e

def delete_product_image(image_url: str):
    """
    Deletes a product image from Supabase storage based on its public URL.
    """
    try:
        # Extract filename from URL
        # URL format usually: https://[project].supabase.co/storage/v1/object/public/product-images/[filename]
        parsed_url = urlparse(image_url)
        path_parts = parsed_url.path.split('/')
        # Find the bucket name in the path and get the next part as the filename
        if BUCKET_NAME in path_parts:
            bucket_idx = path_parts.index(BUCKET_NAME)
            if bucket_idx + 1 < len(path_parts):
                filename = path_parts[bucket_idx + 1]
                supabase_admin.storage.from_(BUCKET_NAME).remove([filename])
    except Exception as e:
        logger.error(f"Error deleting image from Supabase Storage: {e}")
        # We generally don't want to crash the DB transaction if image deletion fails,
        # but we log it as an orphaned file.
        pass
