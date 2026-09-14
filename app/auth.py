from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database.supabase.client import supabase

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    print(f"[AUTH] Received token (first 10 chars): {token[:10]}...")
    if not supabase:
        print("[AUTH] Supabase client is not initialized!")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    try:
        response = supabase.auth.get_user(token)
        if not response.user:
            print("[AUTH] Supabase get_user succeeded but returned no user.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        print(f"[AUTH] Successfully authenticated user: {response.user.email}")
        return response.user
    except Exception as e:
        import traceback
        print(f"[AUTH] Exception during get_user: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
