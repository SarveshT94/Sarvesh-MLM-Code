# -----------------------------------
# Password Hashing
# -----------------------------------
from werkzeug.security import check_password_hash
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify password (supports bcrypt + legacy werkzeug hashes)"""
    try:
        if pwd_context.verify(password, password_hash):
            return True
    except Exception:
        pass

    # Fallback (old hashes)
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


# -----------------------------------
# JWT Token Handling
# -----------------------------------
import jwt
from datetime import datetime, timedelta
from app.config.config import get_config

config = get_config()


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
