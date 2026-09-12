import secrets
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# In-memory verification code store
# ---------------------------------------------------------------------------
# Maps email -> (code, expiry_timestamp)
CODE_STORE: dict[str, tuple[str, float]] = {}
CODE_TTL_SECONDS = 300  # 5 minutes
CODE_DIGITS = 6


def _generate_code() -> str:
    """Generate a 6-digit numeric verification code."""
    return str(secrets.randbelow(10**CODE_DIGITS)).zfill(CODE_DIGITS)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SendCodeRequest(BaseModel):
    email: EmailStr


class SendCodeResponse(BaseModel):
    message: str
    expires_in_seconds: int


class LoginViaCodeRequest(BaseModel):
    email: EmailStr
    code: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="invalid credentials")
    return TokenResponse(access_token="jwt-token-placeholder")


@router.post("/send-code", response_model=SendCodeResponse)
def send_code(payload: SendCodeRequest):
    """Send a 6-digit verification code to the specified email.

    The code is stored in memory with a 5-minute TTL.  Subsequent calls for
    the same email overwrite any existing code and refresh the expiry.
    """
    code = _generate_code()
    expiry = time.time() + CODE_TTL_SECONDS
    CODE_STORE[payload.email] = (code, expiry)

    # Simulate email delivery (production would use SMTP / third-party service)
    print(f"[DEV] Verification code for {payload.email}: {code}")

    return SendCodeResponse(
        message=f"Verification code sent to {payload.email}",
        expires_in_seconds=CODE_TTL_SECONDS,
    )


@router.post("/login/via-code", response_model=TokenResponse)
def login_via_code(payload: LoginViaCodeRequest):
    """Authenticate using email + verification code (one-time use)."""
    stored = CODE_STORE.get(payload.email)

    if stored is None:
        raise HTTPException(
            status_code=401, detail="invalid or expired verification code"
        )

    code, expiry = stored

    # Purge expired codes eagerly on access
    if time.time() > expiry:
        del CODE_STORE[payload.email]
        raise HTTPException(
            status_code=401, detail="invalid or expired verification code"
        )

    if code != payload.code:
        raise HTTPException(
            status_code=401, detail="invalid or expired verification code"
        )

    # One-time consumption — remove immediately on successful match
    del CODE_STORE[payload.email]
    return TokenResponse(access_token="jwt-token-placeholder")
