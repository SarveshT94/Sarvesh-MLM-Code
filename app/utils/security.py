from werkzeug.security import generate_password_hash, check_password_hash
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password):
    # NEW users → bcrypt
    return pwd_context.hash(password)


def verify_password(password_hash, password):
    # Try bcrypt first
    try:
        if pwd_context.verify(password, password_hash):
            return True
    except:
        pass

    # Fallback to old werkzeug hashes
    return check_password_hash(password_hash, password)


import jwt
from datetime import datetime, timedelta
from config import Config

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=Config.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    token = jwt.encode(to_encode, Config.JWT_SECRET, algorithm="HS256")
    return token


def decode_access_token(token: str):
    try:
        decoded = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
