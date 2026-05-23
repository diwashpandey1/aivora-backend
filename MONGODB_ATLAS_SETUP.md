# MongoDB Atlas Setup & TLS/SSL Fix Guide

## Overview

This document covers the MongoDB Atlas TLS/SSL connection fixes for Render deployment. The backend now properly uses MongoDB Atlas with certified TLS encryption.

---

## Changes Made

### 1. **requirements.txt** ✓
Added critical dependencies for MongoDB Atlas:
- `pymongo[srv]>=4.6.0` - SRV record support for mongodb+srv:// URIs
- `dnspython>=2.4.0` - DNS resolution for SRV records
- `certifi>=2024.0.0` - System CA certificate bundle for TLS verification

### 2. **src/database/mongo.py** ✓
Complete rewrite with:
- ✓ TLS/SSL configuration using `certifi.where()`
- ✓ Automatic TLS detection for `mongodb+srv://` URIs
- ✓ Improved timeout handling with `asyncio.wait_for()`
- ✓ Better error logging and debugging
- ✓ Non-blocking connection (doesn't crash backend if MongoDB unavailable)
- ✓ Graceful fallback with `mongo.available` flag

### 3. **src/config.py** ✓
Added MongoDB timeout configuration:
```python
mongodb_connect_timeout_ms: int = 10000  # Connection timeout
mongodb_socket_timeout_ms: int = 10000   # Socket I/O timeout
```

### 4. **.env.example** ✓
Updated with proper MongoDB Atlas URI format and documentation.

---

## Render Deployment Configuration

### Step 1: Update Environment Variables in Render

In your Render service dashboard, set these environment variables:

```
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-firebase-domain.com,http://localhost:5173

MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@cluster.mongodb.net/spam_detector?retryWrites=true&w=majority&tls=true
MONGODB_DATABASE=spam_detector
MONGODB_COLLECTION=scans
MONGODB_SERVER_SELECTION_TIMEOUT_MS=2500
MONGODB_CONNECT_TIMEOUT_MS=10000
MONGODB_SOCKET_TIMEOUT_MS=10000
```

### Step 2: MongoDB Atlas URI Format

Your MONGODB_URI must follow this exact format:

```
mongodb+srv://USERNAME:PASSWORD@cluster-name.mongodb.net/database-name?retryWrites=true&w=majority&tls=true
```

**Replace:**
- `USERNAME` - Your Atlas database user (not email)
- `PASSWORD` - Your Atlas database user password (URL-encoded)
- `cluster-name` - Your cluster name (e.g., `learn-db.xn5nc`)
- `database-name` - Your database name (typically `spam_detector`)

**Example:**
```
mongodb+srv://spam_user:my%40secure%21password@learn-db.xn5nc.mongodb.net/spam_detector?retryWrites=true&w=majority&tls=true
```

### Step 3: MongoDB Atlas Network Access

1. Go to **MongoDB Atlas** → **Network Access**
2. Click **Add IP Address**
3. Select **Allow Access from Anywhere** (Render uses dynamic IPs)
4. Confirm the change

---

## How TLS/SSL Fix Works

### Before (Broken)
```python
self.client = AsyncIOMotorClient(settings.mongodb_uri)
```
- No TLS configuration
- No CA certificate verification
- Fails on Render's Linux environment with `TLSV1_ALERT_INTERNAL_ERROR`

### After (Fixed)
```python
client_options = {
    "tlsCAFile": certifi.where(),  # Use system CA bundle
    "tls": True,
    "serverSelectionTimeoutMS": 2500,
    "connectTimeoutMS": 10000,
    "socketTimeoutMS": 10000,
    "retryWrites": True,
    "w": "majority",
}
self.client = AsyncIOMotorClient(settings.mongodb_uri, **client_options)
```

**Key improvements:**
- ✓ `tlsCAFile=certifi.where()` - Loads correct CA certificates on Linux
- ✓ Auto-detection of `mongodb+srv://` URIs
- ✓ Proper timeout configuration
- ✓ Retry logic enabled

---

## Persistence Features (With Graceful Fallback)

All endpoints check `mongo.available` before using MongoDB:

### `/analyze` Endpoint
```python
if mongo.available:
    scan_id = await repository.create_scan(result)
```
- Saves scan results if MongoDB available
- Returns result without history if unavailable
- Backend remains operational

### `/history` Endpoint
```python
history = await repository.get_history(client_id)
```
- Returns empty list `[]` if MongoDB unavailable
- Frontend displays "No history" gracefully
- No 500 errors

### `/stats` Endpoint
```python
stats = await repository.get_stats()
```
- Returns default stats structure if MongoDB unavailable
- All counts default to 0
- Frontend displays "No data available" gracefully

---

## Troubleshooting

### Issue: `TLSV1_ALERT_INTERNAL_ERROR`
**Solution:** This guide fixes it. Ensure:
1. ✓ `certifi` is installed: `pip install certifi`
2. ✓ URI uses `mongodb+srv://` (not `mongodb://`)
3. ✓ TLS is enabled in connection options
4. ✓ Network access is allowed in MongoDB Atlas

### Issue: `Connection timed out`
**Possible causes:**
1. MongoDB Atlas Network Access not configured for Render
2. Password contains special characters - must be URL-encoded
3. Cluster not running (check MongoDB Atlas dashboard)

**Fix:**
```
# URL-encode password special characters
@ = %40
! = %21
# = %23
$ = %24
% = %25
& = %26
```

### Issue: `Authentication failed`
**Possible causes:**
1. Username or password is incorrect
2. User doesn't have database access permissions
3. Password contains unencoded special characters

**Fix:**
1. Go to **MongoDB Atlas** → **Database Access**
2. Edit the user and reset password
3. Copy password from the connection string (auto-encoded)

### Issue: `Database not found`
**Possible causes:**
1. Database name is incorrect in URI
2. Database doesn't exist in MongoDB Atlas

**Fix:**
1. Create database: Go to **Collections** → **Create Database**
2. Database name must match `MONGODB_DATABASE` in env vars
3. Check connection string has correct database name

### Issue: Backend logs `MongoDB unavailable; persistence is disabled`
**This is expected behavior if:**
- Running locally without MongoDB
- MongoDB is down for maintenance
- Network connectivity issue

**Backend still works!** All endpoints function, just without persistence.

---

## Testing Locally

### Option 1: MongoDB Atlas (Recommended)
1. Update `.env` with your MongoDB Atlas URI
2. Run: `python -m uvicorn src.main:app --reload`
3. Check logs: Should see `✓ Successfully connected to MongoDB`

### Option 2: Local MongoDB
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=spam_detector
MONGODB_COLLECTION=scans
```

Then run local MongoDB:
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

---

## Production Deployment Checklist

- [ ] Update `requirements.txt` with new dependencies
- [ ] Update `.env` with MongoDB Atlas URI
- [ ] Ensure MongoDB Atlas Network Access allows all IPs
- [ ] Test locally first: `pytest tests/`
- [ ] Deploy to Render
- [ ] Check Render logs: Should see `✓ Successfully connected to MongoDB`
- [ ] Test `/history` endpoint from frontend
- [ ] Verify data persists in MongoDB Atlas

---

## Key Environment Variables

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `MONGODB_URI` | string | `mongodb://localhost:27017` | **Must use mongodb+srv:// for Atlas** |
| `MONGODB_DATABASE` | string | `spam_detector` | Database name in Atlas |
| `MONGODB_COLLECTION` | string | `scans` | Collection for scan results |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS` | int | `2500` | Max time to find a server |
| `MONGODB_CONNECT_TIMEOUT_MS` | int | `10000` | Connection establishment timeout |
| `MONGODB_SOCKET_TIMEOUT_MS` | int | `10000` | Socket I/O timeout |

---

## Architecture & Error Handling

### Connection Flow
```
FastAPI Startup
    ↓
lifespan() context manager
    ↓
mongo.connect()
    ↓
AsyncIOMotorClient(uri, **tls_options)
    ↓
admin.ping() verification
    ↓
Create indices
    ↓
Set mongo.available = True
    ↓
Backend ready (with or without persistence)
```

### Error Handling
```
Connection fails → mongo.available = False
                → All endpoints check mongo.available
                → Return default/empty data gracefully
                → Backend keeps running
                → Detailed error in logs
```

---

## Performance Considerations

### Connection Pooling
Motor automatically manages connection pools. On Render free tier:
- Default pool size: 10 connections
- Timeout: 10 seconds (from `connectTimeoutMS`)
- No configuration needed

### Indices Created
```python
[("client_id", 1), ("timestamp", -1)]     # History queries
[("browser_id", 1), ("timestamp", -1)]    # History queries
[("timestamp", -1)]                        # Timeline stats
[("prediction", 1)]                        # Spam/Safe counts
[("detected_type", 1)]                     # SMS/Email type counts
```

These indices optimize the `/history` and `/stats` endpoints.

---

## References

- [MongoDB Atlas Connection String](https://docs.mongodb.com/manual/reference/connection-string/)
- [Motor Async MongoDB Driver](https://motor.readthedocs.io/)
- [PyMongo TLS/SSL Configuration](https://pymongo.readthedocs.io/en/stable/examples/tls.html)
- [Render Environment Variables](https://render.com/docs/environment-variables)
- [Certifi Python Package](https://github.com/certifi/py-certifi)

---

## Support

If you encounter issues:
1. Check MongoDB Atlas dashboard for cluster health
2. Review backend logs on Render
3. Verify environment variables are set correctly
4. Test connection string with MongoDB shell: `mongosh "mongodb+srv://..."`
5. Ensure Network Access is allowed for all IPs (or specific Render IPs)
