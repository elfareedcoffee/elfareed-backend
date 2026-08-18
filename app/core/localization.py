from fastapi import Header
from typing import Optional
from app.db.models.product import LanguageEnum

def get_language(accept_language: Optional[str] = Header(None)) -> LanguageEnum:
    if not accept_language:
        return LanguageEnum.ar
    
    # Simple parse of Accept-Language header, looking for 'ar' or 'en'
    # Fallback to 'ar' if none found
    lang = accept_language.lower()
    if "ar" in lang:
        return LanguageEnum.ar
    if "en" in lang:
        return LanguageEnum.en
        
    return LanguageEnum.ar

def get_localized_translation(translations: list, lang: LanguageEnum):
    if not translations:
        return None
        
    # First try the requested language
    for t in translations:
        if t.language == lang:
            return t
            
    # Then fallback to Arabic
    for t in translations:
        if t.language == LanguageEnum.ar:
            return t
            
    # Finally, fallback to whatever is first
    return translations[0]
