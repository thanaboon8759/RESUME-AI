import time
import asyncio
from typing import Dict, Tuple
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database.supabase.client import supabase

security = HTTPBearer()

# In-memory cache for authenticated users: token -> (user, expire_timestamp)
_TOKEN_CACHE: Dict[str, Tuple[any, float]] = {}
CACHE_TTL_SECONDS = 60.0

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not supabase:
        print("[AUTH] Supabase client is not initialized!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    # Check in-memory cache first to avoid repetitive remote network calls
    now = time.time()
    cached = _TOKEN_CACHE.get(token)
    if cached:
        user, expire_at = cached
        if now < expire_at:
            return user
        else:
            _TOKEN_CACHE.pop(token, None)
    
    try:
        # Run blocking Supabase call in a background thread to prevent blocking the event loop
        response = await asyncio.to_thread(supabase.auth.get_user, token)
        if not response.user:
            print("[AUTH] Supabase get_user succeeded but returned no user.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Cache successful authentication
        _TOKEN_CACHE[token] = (response.user, now + CACHE_TTL_SECONDS)
        if len(_TOKEN_CACHE) > 500:
            _TOKEN_CACHE.clear()
            _TOKEN_CACHE[token] = (response.user, now + CACHE_TTL_SECONDS)
            
        return response.user
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[AUTH] Exception during get_user: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
