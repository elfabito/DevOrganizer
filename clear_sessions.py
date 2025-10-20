#!/usr/bin/env python3
"""
Clear all Flask session data from Redis
Run this script to clean up corrupted session data
"""
import os
import redis
from dotenv import load_dotenv

load_dotenv('.env')

redis_url = os.getenv('REDIS_URL')
if not redis_url:
    print("ERROR: REDIS_URL not found in .env")
    exit(1)

print(f"Connecting to Redis...")
r = redis.from_url(redis_url, decode_responses=False)

try:
    r.ping()
    print("✓ Connected to Redis")
except Exception as e:
    print(f"✗ Failed to connect: {e}")
    exit(1)

# Find all session keys (Flask-Session uses 'session:' prefix by default)
# With SESSION_KEY_PREFIX='devorg:', they'll be 'devorg:session:*'
patterns = ['session:*', 'devorg:session:*', 'flask_session:*']

total_deleted = 0
for pattern in patterns:
    print(f"\nSearching for pattern: {pattern}")
    keys = r.keys(pattern)
    if keys:
        print(f"Found {len(keys)} session keys")
        deleted = r.delete(*keys)
        total_deleted += deleted
        print(f"✓ Deleted {deleted} keys")
    else:
        print(f"No keys found for pattern {pattern}")

print(f"\n{'='*50}")
print(f"Total sessions deleted: {total_deleted}")
print(f"{'='*50}")

if total_deleted > 0:
    print("\n✓ Session cleanup complete!")
    print("Users will need to log in again.")
else:
    print("\nNo sessions found to delete.")
