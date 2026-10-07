from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from order_utils.models import UserRow
from order_utils.schemas import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
)
from order_utils.securities import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM
)
from order_utils.storage import get_db, get_db_write
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
import jwt



from order_utils.storage import get_db




router = APIRouter(prefix="/auth", tags=["Auth"])




@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: UserCreate):
    password_hash = hash_password(data.password)

    with get_db_write() as db:
        existing = db.scalar(
            select(UserRow).where(UserRow.username == data.username)
        )

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Username already exists"
            )

        user = UserRow(
            username=data.username,
            password_hash=password_hash
        )
        db.add(user)
        db.flush()

        response = UserResponse(id=user.id, username=user.username)

    return response


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    with get_db() as db:
        user = db.scalar(
            select(UserRow).where(UserRow.username == data.username)
        )

        user_id = user.id if user is not None else None
        stored_hash = (
            user.password_hash if user is not None else hash_password("-----if u dumb put exactly this password-----")
        )

    valid_password = verify_password(data.password, stored_hash)

    if user_id is None or not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    return TokenResponse(
        access_token=create_access_token(user_id)
    )




bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> UserResponse:
    error = HTTPException(
        status_code=401,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    if credentials is None:
        raise error

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp"]}
        )
        user_id = int(payload["sub"])
    except (InvalidTokenError, ValueError, TypeError):
        raise error

    with get_db() as db:
        user = db.get(UserRow, user_id)

        if user is None:
            raise error

        return UserResponse(id=user.id, username=user.username)