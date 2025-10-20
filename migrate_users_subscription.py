"""
Migration Script: Add Subscription Fields to Existing Users
Run this script ONCE after deploying the subscription system to update existing users.
"""
import os
import redis
import json
from dotenv import load_dotenv
from datetime import datetime, timezone

# Load environment variables
load_dotenv('.env')

def migrate_users():
    """Add subscription fields to all existing users in Redis"""

    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        print("❌ ERROR: REDIS_URL not found in .env file")
        return

    try:
        # Connect to Redis
        r = redis.from_url(redis_url, decode_responses=True)
        print("✅ Connected to Redis")

        # Get all user keys
        user_keys = r.keys('user:*')
        print(f"\n📊 Found {len(user_keys)} users to migrate")

        if not user_keys:
            print("ℹ️  No users found in Redis. Nothing to migrate.")
            return

        # Ask for confirmation
        response = input(f"\n⚠️  This will update {len(user_keys)} user(s). Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Migration cancelled")
            return

        # Migrate each user
        updated_count = 0
        skipped_count = 0

        for key in user_keys:
            user_data = json.loads(r.get(key))
            user_id = user_data.get('id', key.split(':')[1])

            # Check if user already has subscription fields
            if 'plan_type' in user_data:
                print(f"⏭️  Skipping {user_data.get('email')} - already has subscription fields")
                skipped_count += 1
                continue

            # Add subscription fields
            user_data['plan_type'] = 'free'
            user_data['stripe_customer_id'] = None
            user_data['stripe_subscription_id'] = None
            user_data['subscription_status'] = None
            user_data['subscription_current_period_end'] = None
            user_data['trial_end'] = None
            user_data['updated_at'] = datetime.now(timezone.utc).isoformat()

            # Save updated user
            r.set(key, json.dumps(user_data))
            print(f"✅ Migrated {user_data.get('email')} → Free plan")
            updated_count += 1

        print(f"\n{'='*60}")
        print(f"🎉 Migration Complete!")
        print(f"   ✅ Updated: {updated_count} user(s)")
        print(f"   ⏭️  Skipped: {skipped_count} user(s) (already migrated)")
        print(f"   📊 Total:   {len(user_keys)} user(s)")
        print(f"{'='*60}\n")

    except redis.exceptions.ConnectionError as e:
        print(f"❌ ERROR: Could not connect to Redis")
        print(f"   Make sure Redis is running and REDIS_URL is correct")
        print(f"   Error: {str(e)}")
    except Exception as e:
        print(f"❌ ERROR during migration: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  DevOrganizer - User Subscription Migration Script")
    print("="*60 + "\n")
    print("This script will add subscription fields to existing users:")
    print("  • plan_type: 'free'")
    print("  • stripe_customer_id: None")
    print("  • stripe_subscription_id: None")
    print("  • subscription_status: None")
    print("  • subscription_current_period_end: None")
    print("  • trial_end: None\n")

    migrate_users()
