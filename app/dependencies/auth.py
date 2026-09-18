from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError

from app.core.jwt_service import JWTService

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user_token(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return creds.credentials


def get_current_user_from_access_token(token: str = Depends(get_current_user_token)) -> dict:
    try:
        payload = JWTService.validate_access_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    return payload
