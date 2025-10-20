# Redis Database Setup Guide

## Overview
Your DevOrganizer app now supports **both SQLite and Redis** databases. The app will automatically detect which database to use based on your environment configuration.

## What Was Added

### 1. Dependencies
Added to [requirements.txt](requirements.txt):
- `redis>=5.0.0` - Redis client for Python
- `Flask-Session>=0.5.0` - Server-side session management

### 2. Complete Redis Implementation

#### RedisProjectStorage
Located in [storage_redis.py](storage_redis.py), this class now includes:
- ✅ Project CRUD operations
- ✅ Weekly summaries (create, update, delete, get by project)
- ✅ Estimations (save, get, update, delete, load by user)
- ✅ Feature suggestions
- ✅ Section states (for collapsible UI)

#### RedisUserStorage
New class in [storage_redis.py](storage_redis.py) that handles:
- ✅ User authentication (create, get by ID/email)
- ✅ Password management
- ✅ Last login tracking
- ✅ ClickUp token storage

### 3. Environment Configuration
Created [.env.example](.env.example) with Redis configuration template.

### 4. Smart Fallback
[app.py](app.py) now intelligently:
- Tries to connect to Redis if `REDIS_URL` is set
- Falls back to SQLite if Redis is unavailable
- Logs which database system is being used

## Installation Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Install Redis Server

**Windows:**
```bash
# Using Chocolatey
choco install redis-64

# Or download from: https://github.com/microsoftarchive/redis/releases
```

**Linux/macOS:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS with Homebrew
brew install redis
```

### Step 3: Start Redis
```bash
# Windows
redis-server

# Linux/macOS
sudo systemctl start redis
# or
redis-server
```

### Step 4: Configure Environment
Create a `.env` file from the template:
```bash
cp .env.example .env
```

Edit `.env` and set your Redis URL:
```env
# For local Redis without password:
REDIS_URL=redis://localhost:6379/0

# For Redis with password:
REDIS_URL=redis://:your-password@localhost:6379/0

# For Redis Cloud or remote:
REDIS_URL=redis://:password@host:port/0
```

### Step 5: Run Your App
```bash
python app.py
```

Check the console output - you should see:
```
✓ Using Redis for data storage
```

## Testing Redis Connection

Run the test script:
```bash
python check_redis.py
```

This will verify your Redis connection and show sample data.

## Switching Between Databases

### To Use Redis:
Set `REDIS_URL` in your `.env` file:
```env
REDIS_URL=redis://localhost:6379/0
```

### To Use SQLite:
Comment out or remove `REDIS_URL` from `.env`:
```env
# REDIS_URL=redis://localhost:6379/0
```

The app will automatically fall back to SQLite.

## Redis Data Structure

Your data is organized in Redis with these key patterns:

### Projects
- `project:{project_id}` - Project data as JSON
- `user_projects:{user_id}` - Set of project IDs for a user

### Users
- `user:{user_id}` - User data as JSON
- `user_email:{email}` - Index mapping email to user_id

### Weekly Summaries
- `weekly:{summary_id}` - Weekly summary as JSON
- `project_weekly:{project_id}` - List of summary IDs for a project

### Estimations
- `estimation:{estimation_id}` - Estimation data as JSON
- `user_estimations:{user_id}` - Set of estimation IDs for a user

### Section States
- `section_state:{user_id}:{project_id}` - Hash of section states

## Troubleshooting

### Redis Connection Failed
**Error:** `Failed to connect to Redis, falling back to SQLite`

**Solutions:**
1. Check if Redis is running: `redis-cli ping` (should return "PONG")
2. Verify `REDIS_URL` format in `.env`
3. Check firewall settings
4. For Windows, ensure Redis service is started

### Port Already in Use
**Error:** `Address already in use`

**Solution:** Change the Redis port in `redis.conf` or your `REDIS_URL`

### Permission Denied
**Error:** `Permission denied connecting to Redis`

**Solution:**
- Linux/macOS: `sudo systemctl start redis`
- Check Redis configuration file permissions

## Data Migration

To migrate existing SQLite data to Redis, you can create a migration script:

```python
# Example migration script
from storage_sqlite import ProjectStorageSQLite
from storage_redis import RedisProjectStorage, RedisUserStorage
import redis

# Connect to both databases
sqlite_storage = ProjectStorageSQLite('projects.db')
redis_client = redis.from_url('redis://localhost:6379/0', decode_responses=True)
redis_storage = RedisProjectStorage(redis_client)
redis_user_storage = RedisUserStorage(redis_client)

# Migrate users
# Migrate projects
# Migrate estimations
# etc.
```

## Benefits of Redis

✅ **Performance:** In-memory data store is much faster than disk-based SQLite
✅ **Scalability:** Better for multi-user concurrent access
✅ **Sessions:** Native support for distributed sessions
✅ **Caching:** Built-in expiration and cache capabilities
✅ **Production Ready:** Industry standard for high-traffic applications

## Need Help?

- Redis Documentation: https://redis.io/docs/
- Redis Python Client: https://redis-py.readthedocs.io/
- Check [storage_redis.py](storage_redis.py) for implementation details
