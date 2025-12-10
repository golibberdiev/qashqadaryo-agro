# schemas.py
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ---------- AUTH / USER ----------
class Token(BaseModel):
    access_token: str
    token_type: str


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str
    cluster_code: str


class UserOut(UserBase):
    id: int
    role: str
    cluster_code: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ---------- KLASTER REPORT ----------
class ClusterReportBase(BaseModel):
    year: int
    production: float
    export: float
    employment: int
    profitability: float
    trend_production: float
    trend_export: float
    trend_employment: float
    trend_profitability: float


class ClusterReportCreate(ClusterReportBase):
    pass


# ---------- KLASTER + USER RO'YXATDAN O'TISH ----------
class ClusterRegisterRequest(BaseModel):
    username: str
    password: str
    district_code: str
    cluster_type: str
    cluster_name: str
    leader_name: Optional[str] = None
    leader_phone: Optional[str] = None


class ClusterRegisterResponse(BaseModel):
    username: str
    cluster_code: str
    district_code: str
    cluster_type: str
    cluster_name: str
    leader_name: Optional[str] = None
    leader_phone: Optional[str] = None


# ---------- ADMIN UCHUN KLASTER RO'YXATI ----------
class AdminClusterItem(BaseModel):
    district_code: str
    district_name: str
    cluster_code: str
    cluster_name: str
    cluster_type: str
    leader_name: Optional[str] = None
    leader_phone: Optional[str] = None
    user_username: Optional[str] = None
    is_active: bool
    total_reports: int
    model_config = ConfigDict(from_attributes=False)
class ClusterAdminView(BaseModel):
    id: int
    name: str
    district: str
    cluster_type: str | None
    leader_name: str | None
    leader_phone: str | None
    status: str
    admin_comment: str | None

    class Config:
        from_attributes = True
