import bcrypt
from werkzeug.security import check_password_hash
import jwt
from datetime import datetime, timedelta
from app.config.config import get_config

config = get_config()

# -----------------------------------
# Password Hashing (Upgraded to Native Bcrypt)
# -----------------------------------

def hash_password(password: str) -> str:
    """Hash password using native bcrypt (bypassing broken passlib)"""
    # bcrypt requires bytes, so we encode to utf-8 first
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    # Return as a standard string for the database
    return hashed_bytes.decode('utf-8')


def verify_password(password_hash: str, password: str) -> bool:
    """Verify password against native bcrypt or legacy werkzeug hashes"""
    # 1. Try Native Bcrypt (Modern users)
    try:
        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            return True
    except Exception:
        pass

    # 2. Try Fallback (Extremely old hashes)
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


# -----------------------------------
# JWT Token Handling
# -----------------------------------

def create_access_token(data: dict) -> str:
    """Generate JWT token"""
    try:
        to_encode = data.copy()

        now = datetime.utcnow()
        expire = now + timedelta(minutes=config.JWT_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": now,
            "type": "access"   # future-proofing
        })

        token = jwt.encode(
            to_encode,
            config.JWT_SECRET,
            algorithm="HS256"
        )

        return token

    except Exception as e:
        raise RuntimeError(f"Token creation failed: {str(e)}")


def decode_access_token(token: str):
    """Decode JWT token with strict validation"""
    try:
        decoded = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=["HS256"]
        )

        # Optional: enforce token type
        if decoded.get("type") != "access":
            return None

        return decoded

    except jwt.ExpiredSignatureError:
        return None

    except jwt.InvalidTokenError:
        return None

    except Exception:
        return None
