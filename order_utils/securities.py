from pwdlib import PasswordHash

from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
import os
from pathlib import Path






load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.environ["ALGORITHM"]







password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)







def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=5)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)



