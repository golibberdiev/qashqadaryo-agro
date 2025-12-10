# auth.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User, Cluster, District

# ============================================================
#  JWT sozlamalari
# ============================================================

SECRET_KEY = "qashqadaryo-agrocluster-super-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 kun

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

router = APIRouter(prefix="/auth", tags=["Auth"])


# ============================================================
#  Yordamchi funksiyalar
# ============================================================

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ============================================================
#  Joriy foydalanuvchini olish (Bearer token orqali)
# ============================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token noto‘g‘ri yoki muddati tugagan.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin huquqi talab etiladi.")
    return current_user


# ============================================================
#  LOGIN endpoint (admin + klaster)
# ============================================================

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Admin va klaster foydalanuvchilari uchun umumiy login.
    Front va Swaggerdan:
      - username
      - password
    form-urlencoded ko‘rinishida yuboriladi.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Login yoki parol noto‘g‘ri.")

    # --- Agar bu klaster foydalanuvchisi bo‘lsa, klaster holatini tekshiramiz
    if user.role == "cluster" and user.cluster_id is not None:
        cluster = db.query(Cluster).filter(Cluster.id == user.cluster_id).first()

        if cluster:
            # Rad etilgan holat
            if getattr(cluster, "status", None) == "rejected":
                comment = getattr(cluster, "admin_comment", None)
                msg = "Ro‘yxatdan o‘tish so‘rovingiz rad etilgan."
                if comment:
                    msg += f" Izoh: {comment}"
                else:
                    msg += " Sabab ko‘rsatilmagan."
                raise HTTPException(
                    status_code=403,
                    detail=msg
                )

            # Hali tasdiqlanmagan holat (pending / faollashtirilmagan)
            if getattr(cluster, "status", None) in (None, "pending") or not getattr(cluster, "is_active", False):
                raise HTTPException(
                    status_code=403,
                    detail="Ro‘yxatdan o‘tish so‘rovingiz hali tasdiqlanmagan. Viloyat admini tasdiqlaganidan keyin tizimga kira olasiz."
                )

    # --- Admin yoki tasdiqlangan klaster bo‘lsa, token beramiz
    access_token = create_access_token({"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "cluster_id": user.cluster_id,
        "username": user.username,
    }


# ============================================================
#  KLASTER RO‘YXATDAN O‘TISH endpoint
# ============================================================

class ClusterRegisterIn(BaseModel):
    username: str
    password: str
    district_code: str
    cluster_type: Optional[str] = None
    cluster_name: str
    leader_name: str
    leader_phone: Optional[str] = None


@router.post("/register-cluster")
def register_cluster(
    payload: ClusterRegisterIn,
    db: Session = Depends(get_db),
):
    """
    Yangi agroklasterni ro‘yxatdan o‘tkazish:
      - Cluster(status='pending', is_active=False)
      - User(role='cluster', cluster_id=cluster.id)
    Admin tasdiqlamaguncha klaster panelga kira olmaydi.
    """
    # 1. Login band emasligini tekshirish
    existing_user = db.query(User).filter(User.username == payload.username).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Bu login allaqachon band. Iltimos, boshqa login tanlang.",
        )

    # 2. Tuman kodini tekshirish (District jadvali bo‘lsa)
    district = db.query(District).filter(District.code == payload.district_code).first()
    if not district:
        raise HTTPException(
            status_code=400,
            detail="Tuman kodi noto‘g‘ri (District jadvalidan topilmadi).",
        )

    # 3. Klasterni yaratish
    cluster = Cluster(
        name=payload.cluster_name,
        district_code=payload.district_code,
        cluster_type=payload.cluster_type,
        leader_name=payload.leader_name,
        leader_phone=payload.leader_phone,
        status="pending",
        is_active=False,
        admin_comment=None,
    )
    db.add(cluster)
    db.flush()  # cluster.id

    # 4. Klasterning asosiy foydalanuvchisi
    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        role="cluster",
        cluster_id=cluster.id,
    )
    db.add(user)

    db.commit()
    db.refresh(cluster)

    return {
        "message": "Ro‘yxatdan o‘tish so‘rovi qabul qilindi. Viloyat admini tasdiqlagach tizimga kira olasiz.",
        "cluster_id": cluster.id,
    }
