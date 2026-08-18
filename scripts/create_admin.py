"""
Admin User Seed Script
======================
Creates an admin user in both Supabase Auth and the local database.

Usage:
    python scripts/create_admin.py

Set the following in your .env before running:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DATABASE_URL
"""

import sys
import uuid
from pathlib import Path

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.db.models.admin import AdminUser, AdminRole
from app.core.supabase import supabase

# ── Configure your new admin user here ──────────────────────────────────────
ADMIN_EMAIL    = "admin@elfareedcoffee.com"
ADMIN_PASSWORD = "El2@26@Fareed\\"
ADMIN_USERNAME = "admin"
ADMIN_NAME     = "مدير المتجر"
ADMIN_PHONE    = "+201100917301"         # OTP will be sent here
ADMIN_ROLE     = AdminRole.SUPER_ADMIN
# ────────────────────────────────────────────────────────────────────────────


def main():
    print("🔧 Creating admin user...")

    from app.core.config import settings
    # 1. Create user in Supabase Auth (using the service-role client to bypass email confirmation)
    if "your-project.supabase.co" in settings.SUPABASE_URL:
        print("⚠️  Placeholder Supabase URL detected. Bypassing Supabase Auth creation...")
        supabase_user_id = str(uuid.uuid4())
    else:
        try:
            auth_res = supabase.auth.admin.create_user({
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "email_confirm": True,      # Skip the confirmation email
            })
            supabase_user_id = str(auth_res.user.id)
            print(f"✅ Supabase Auth user created: {supabase_user_id}")
        except Exception as e:
            print(f"❌ Supabase Auth error: {e}")
            print("   → The user might already exist in Supabase Auth.")
            print("   → If so, grab their UUID from the Supabase dashboard and hard-code it below.")
            sys.exit(1)

    # 2. Insert into local DB
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter(AdminUser.username == ADMIN_USERNAME).first()
        if existing:
            print(f"⚠️  Admin '{ADMIN_USERNAME}' already exists in the database.")
            return

        admin = AdminUser(
            id=uuid.uuid4(),
            auth_user_id=uuid.UUID(supabase_user_id),
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            phone_number=ADMIN_PHONE,
            name=ADMIN_NAME,
            role=ADMIN_ROLE,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"✅ Admin user '{ADMIN_USERNAME}' inserted into database.")
        print()
        print("─" * 50)
        print(f"  URL:       http://localhost:8080/admin")
        print(f"  Username:  {ADMIN_USERNAME}")
        print(f"  Password:  {ADMIN_PASSWORD}")
        print(f"  OTP sent to: {ADMIN_PHONE}")
        print("─" * 50)
    except Exception as e:
        db.rollback()
        print(f"❌ Database error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
