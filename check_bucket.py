import asyncio
from app.core.supabase import supabase_admin

def check_bucket():
    try:
        bucket_name = "product-images"
        print(f"Checking if bucket '{bucket_name}' exists...")
        buckets = supabase_admin.storage.list_buckets()
        
        found = False
        for b in buckets:
            if b.name == bucket_name:
                found = True
                print(f"Bucket '{bucket_name}' exists. Public: {b.public}")
                if not b.public:
                    print("Updating bucket to be public...")
                    supabase_admin.storage.update_bucket(bucket_name, public=True)
                    print("Bucket is now public.")
                break
                
        if not found:
            print(f"Bucket '{bucket_name}' not found. Creating it as public...")
            supabase_admin.storage.create_bucket(bucket_name, public=True)
            print("Bucket created.")
            
    except Exception as e:
        print(f"Error checking bucket: {e}")

if __name__ == "__main__":
    check_bucket()
