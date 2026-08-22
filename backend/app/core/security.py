from fastapi import Header, HTTPException, status

def verify_api_key(api_key: str = Header(None)):
    if api_key and api_key == "invalid_key":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key
