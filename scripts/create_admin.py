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
from app.core.supabase import supabase_admin

# ── Configure your new admin user here ──────────────────────────────────────
ADMIN_EMAIL    = "elfareedcoffee@gmail.com"
ADMIN_PASSWORD = "El2@26@Fareed\\"
ADMIN_USERNAME = "admin"
ADMIN_NAME     = "مدير المتجر"
ADMIN_PHONE    = "+201100917301"         # OTP will be sent here
ADMIN_ROLE     = AdminRole.SUPER_ADMIN
# ────────────────────────────────────────────────────────────────────────────


def main():
    print("🔧 Creating / syncing admin user...")

    from app.core.config import settings
    # 1. Create or retrieve user in Supabase Auth (using the service-role client)
    if "your-project.supabase.co" in settings.SUPABASE_URL:
        print("⚠️  Placeholder Supabase URL detected. Bypassing Supabase Auth creation...")
        supabase_user_id = str(uuid.uuid4())
    else:
        try:
            auth_res = supabase_admin.auth.admin.create_user({
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "email_confirm": True,      # Skip the confirmation email
                "user_metadata": {"name": ADMIN_NAME}
            })
            supabase_user_id = str(auth_res.user.id)
            print(f"✅ Supabase Auth user created: {supabase_user_id}")
        except Exception as e:
            print(f"ℹ️  Supabase Auth create notice: {e}")
            print("   → Attempting to retrieve existing user from Supabase Auth...")
            try:
                # Find user by list_users
                users = supabase_admin.auth.admin.list_users()
                target_user = next((u for u in users if u.email.lower() == ADMIN_EMAIL.lower()), None)
                if target_user:
                    supabase_user_id = str(target_user.id)
                    # Update password to ensure it matches
                    supabase_admin.auth.admin.update_user_by_id(supabase_user_id, {
                        "password": ADMIN_PASSWORD,
                        "email_confirm": True
                    })
                    print(f"✅ Supabase Auth user synced: {supabase_user_id}")
                else:
                    print("❌ Could not find or create user in Supabase Auth.")
                    sys.exit(1)
            except Exception as e2:
                print(f"❌ Error during fallback: {e2}")
                sys.exit(1)

    # 2. Insert or update in local DB
    db = SessionLocal()
    try:
        existing = db.query(AdminUser).filter(
            (AdminUser.username == ADMIN_USERNAME) | (AdminUser.email == ADMIN_EMAIL)
        ).first()

        if existing:
            existing.auth_user_id = uuid.UUID(supabase_user_id)
            existing.username = ADMIN_USERNAME
            existing.email = ADMIN_EMAIL
            existing.phone_number = ADMIN_PHONE
            existing.name = ADMIN_NAME
            existing.role = ADMIN_ROLE
            existing.is_active = True
            db.commit()
            print(f"✅ Admin user '{ADMIN_USERNAME}' updated in database.")
        else:
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
        print(f"  Username:  {ADMIN_USERNAME}")
        print(f"  Email:     {ADMIN_EMAIL}")
        print(f"  Password:  {ADMIN_PASSWORD}")
        print(f"  Role:      {ADMIN_ROLE.value}")
        print("─" * 50)
    except Exception as e:
        db.rollback()
        print(f"❌ Database error: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
