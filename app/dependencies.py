from typing import Generator, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.database.models import User
from app.core.security import decode_access_token


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        # Check authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        # Default development engineer user if no session cookie exists
        dev_user = db.query(User).filter(User.email == "engineer@cadcopilot.internal").first()
        if not dev_user:
            from app.core.security import hash_password
            dev_user = User(
                email="engineer@cadcopilot.internal",
                full_name="Chief Systems Engineer",
                hashed_password=hash_password("admin123"),
                role="engineer"
            )
            db.add(dev_user)
            db.commit()
            db.refresh(dev_user)
        return dev_user

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    return user


def get_current_user(user: Optional[User] = Depends(get_current_user_optional)) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )
    return user
