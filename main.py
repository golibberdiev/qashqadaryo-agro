# main.py
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import District, Cluster, User, ClusterReport
from auth import router as auth_router, get_current_user, get_admin_user, get_password_hash

# ============================================================
#  FastAPI ilovasi
# ============================================================

app = FastAPI(
    title="Qashqadaryo agroklaster backend",
    version="0.2.0",
    description="Klaster panel, admin panel va viloyat paneli uchun backend"
)

# CORS (browserdan localhostdan kelayotgan so‘rovlar uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://agroqashqadaryo.netlify.app",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routerini ulaymiz: /auth/login, /auth/register-cluster va hok.
app.include_router(auth_router)


# ============================================================
#  Startup: jadval yaratish + admin va tumanlarni seed qilish
# ============================================================

@app.on_event("startup")
def on_startup():
    # 1. Jadval strukturasini yaratish
    Base.metadata.create_all(bind=engine)

    # 2. Admin foydalanuvchi va tumanlarni seed qilish
    db: Session = next(get_db())
    try:
        # Admin user (login: admin, parol: admin)
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                hashed_password=get_password_hash("admin"),
                role="admin",
                cluster_id=None,
                created_at=datetime.utcnow(),
            )
            db.add(admin)
            print("[SEED] Admin foydalanuvchi yaratildi: admin/admin")

        # Tumanlar (agar yo‘q bo‘lsa)
        districts_seed = [
            ("qarshi", "Qarshi tumani"),
            ("kasbi", "Kasbi tumani"),
            ("nishon", "Nishon tumani"),
            ("mirishkor", "Mirishkor tumani"),
            ("kitob", "Kitob tumani"),
            ("shahrisabz", "Shahrisabz tumani"),
            ("guzor", "G‘uzor tumani"),
        ]
        for code, name in districts_seed:
            if not db.query(District).filter(District.code == code).first():
                db.add(District(code=code, name=name))
        db.commit()
    finally:
        db.close()


# ============================================================
#  Model: joriy foydalanuvchi (faqat type hint uchun)
# ============================================================

# Agar sizning models.py ichida User klassi bo‘lsa, shundan foydalanamiz.
# get_current_user shuni qaytaradi.

# ============================================================
#  Cluster report – klaster xodimi uchun
# ============================================================

class ClusterReportIn(BaseModel):
    year: int
    production: float
    export: float
    employment: int
    profitability: float


class ClusterReportOut(BaseModel):
    year: int
    production: float
    export: float
    employment: int
    profitability: float

    class Config:
        from_attributes = True  # Pydantic v2


@app.get("/api/cluster-report", response_model=Optional[ClusterReportOut])
def get_my_cluster_report(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Joriy klaster foydalanuvchisi uchun tanlangan yil bo‘yicha hisobotni qaytaradi.
    """
    if current_user.role != "cluster":
        raise HTTPException(status_code=403, detail="Faqat klaster foydalanuvchilari uchun.")

    report = (
        db.query(ClusterReport)
        .filter(
            ClusterReport.cluster_id == current_user.cluster_id,
            ClusterReport.year == year,
        )
        .first()
    )
    return report


@app.post("/api/cluster-report", response_model=ClusterReportOut)
def upsert_my_cluster_report(
    payload: ClusterReportIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Joriy klaster foydalanuvchisi uchun yillik hisobotni yaratish/yoki yangilash.
    """
    if current_user.role != "cluster":
        raise HTTPException(status_code=403, detail="Faqat klaster foydalanuvchilari uchun.")

    if current_user.cluster_id is None:
        raise HTTPException(status_code=400, detail="Foydalanuvchi biror klasterga biriktirilmagan.")

    cluster = db.query(Cluster).filter(Cluster.id == current_user.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Klaster topilmadi.")

    # Faqat tasdiqlangan klaster ma’lumot kiritishi mumkin
    if cluster.status != "approved" or not getattr(cluster, "is_active", False):
        raise HTTPException(
            status_code=403,
            detail="Klasteringiz hali tasdiqlanmagan yoki faollashtirilmagan."
        )

    report = (
        db.query(ClusterReport)
        .filter(
            ClusterReport.cluster_id == current_user.cluster_id,
            ClusterReport.year == payload.year,
        )
        .first()
    )

    if not report:
        # E’TIBOR BERING: created_at argumenti olib tashlandi
        report = ClusterReport(
            cluster_id=current_user.cluster_id,
            year=payload.year,
            production=payload.production,
            export=payload.export,
            employment=payload.employment,
            profitability=payload.profitability,
        )
        db.add(report)
    else:
        report.production = payload.production
        report.export = payload.export
        report.employment = payload.employment
        report.profitability = payload.profitability

    db.commit()
    db.refresh(report)
    return report


# ============================================================
#  Viloyat paneli uchun agregatsiya – /api/agrodata
#  Strukturasi: { "2025": { "kasbi": [ {id, name, production,...}, ... ] }, ... }
# ============================================================

@app.get("/api/agrodata")
def get_agrodata(db: Session = Depends(get_db)) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    Viloyat paneli uchun barcha yillar bo‘yicha:
    {
      "2025": {
        "kasbi": [
          {
            "id": 1,
            "name": "...",
            "district": "Kasbi tumani",
            "production": ...,
            "export": ...,
            "employment": ...,
            "profitability": ...,
            "trend": { "production": 0, "export": 0, "employment": 0, "profitability": 0 }
          },
          ...
        ],
        ...
      },
      ...
    }
    Faqat tasdiqlangan va aktiv klasterlar olinadi.
    """
    # ClusterReport + Cluster + District join
    rows = (
        db.query(ClusterReport, Cluster, District)
        .join(Cluster, Cluster.id == ClusterReport.cluster_id)
        .join(District, District.code == Cluster.district_code, isouter=True)
        .filter(Cluster.status == "approved", Cluster.is_active == True)  # noqa: E712
        .all()
    )

    data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for report, cluster, district in rows:
        year_key = str(report.year)
        dist_code = cluster.district_code or "unknown"

        year_dict = data.setdefault(year_key, {})
        dist_list = year_dict.setdefault(dist_code, [])

        dist_list.append({
            "id": cluster.id,
            "name": cluster.name,
            "district": district.name if district else dist_code,
            "production": float(report.production or 0),
            "export": float(report.export or 0),
            "employment": int(report.employment or 0),
            "profitability": float(report.profitability or 0),
            # hozircha trendlarni 0 qilib beramiz – front-end default bilan ishlaydi
            "trend": {
                "production": 0,
                "export": 0,
                "employment": 0,
                "profitability": 0,
            },
        })

    return data


# ============================================================
#  Admin endpointlari
# ============================================================

class AdminDecision(BaseModel):
    cluster_id: int
    comment: Optional[str] = None


@app.get("/api/admin/pending-clusters", dependencies=[Depends(get_admin_user)])
def get_pending_clusters(db: Session = Depends(get_db)):
    """
    Tasdiqlash kutilayotgan klasterlar ro'yxati.
    Telefon raqami, login va ro'yxatdan o'tgan sana bilan.
    """
    rows = (
        db.query(Cluster, User, District)
        .join(User, User.cluster_id == Cluster.id)
        .join(District, District.code == Cluster.district_code, isouter=True)
        .filter(Cluster.status == "pending")
        .all()
    )

    result = []
    for cluster, user, district in rows:
        result.append({
            "id": cluster.id,
            "cluster_name": cluster.name,
            "district_code": cluster.district_code,
            "district_name": district.name if district else None,
            "cluster_type": cluster.cluster_type,
            "leader_name": cluster.leader_name,
            "leader_phone": cluster.leader_phone,
            "status": cluster.status,
            "created_at": getattr(cluster, "created_at", None).isoformat()
                if getattr(cluster, "created_at", None) else None,
            "username": user.username,
        })
    return result


@app.get("/api/admin/cluster-history/{cluster_id}", dependencies=[Depends(get_admin_user)])
def get_cluster_history(cluster_id: int, db: Session = Depends(get_db)):
    """
    Admin uchun: klasterning ro'yxatdan o'tish ma'lumotlari va hisobotlar tarixi.
    Parollar qaytarilmaydi.
    """
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Klaster topilmadi.")

    user = db.query(User).filter(User.cluster_id == cluster_id).first()

    reports = (
        db.query(ClusterReport)
        .filter(ClusterReport.cluster_id == cluster_id)
        .order_by(ClusterReport.year.desc())
        .all()
    )

    return {
        "cluster": {
            "id": cluster.id,
            "name": cluster.name,
            "district_code": cluster.district_code,
            "cluster_type": cluster.cluster_type,
            "leader_name": cluster.leader_name,
            "leader_phone": cluster.leader_phone,
            "status": cluster.status,
            "admin_comment": getattr(cluster, "admin_comment", None),
            "created_at": getattr(cluster, "created_at", None).isoformat()
                if getattr(cluster, "created_at", None) else None,
        },
        "user": {
            "username": user.username if user else None,
            "created_at": getattr(user, "created_at", None).isoformat()
                if (user and getattr(user, "created_at", None)) else None,
        },
        "reports": [
            {
                "year": r.year,
                "production": r.production,
                "export": r.export,
                "employment": r.employment,
                "profitability": r.profitability,
                "created_at": getattr(r, "created_at", None).isoformat()
                    if getattr(r, "created_at", None) else None,
            }
            for r in reports
        ],
    }


@app.post("/api/admin/cluster-approve", dependencies=[Depends(get_admin_user)])
def approve_cluster(decision: AdminDecision, db: Session = Depends(get_db)):
    """
    Klasterni tasdiqlash.
    status -> 'approved', is_active -> True
    comment bo'lsa, admin_comment ga yoziladi.
    """
    cluster = db.query(Cluster).filter(Cluster.id == decision.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Klaster topilmadi.")

    cluster.status = "approved"
    cluster.is_active = True
    if decision.comment:
        cluster.admin_comment = decision.comment

    db.commit()
    return {"message": "Klaster tasdiqlandi."}


@app.post("/api/admin/cluster-reject", dependencies=[Depends(get_admin_user)])
def reject_cluster(decision: AdminDecision, db: Session = Depends(get_db)):
    """
    Klasterni rad etish.
    status -> 'rejected', is_active -> False, admin_comment majburiy.
    """
    if not decision.comment:
        raise HTTPException(status_code=400, detail="Rad etishda izoh majburiy.")

    cluster = db.query(Cluster).filter(Cluster.id == decision.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Klaster topilmadi.")

    cluster.status = "rejected"
    cluster.is_active = False
    cluster.admin_comment = decision.comment

    db.commit()
    return {"message": "Klaster ro‘yxatdan o‘tish so‘rovi rad etildi."}

# ====================== YANGI ADMIN API-lar ============================

class BlockRequest(BaseModel):
    cluster_id: int
    blocked: bool = True


@app.get("/api/admin/active-clusters", dependencies=[Depends(get_admin_user)])
def get_active_clusters(db: Session = Depends(get_db)):
    """
    Ro'yxatdan o'tgan klasterlar ro'yxati (tasdiqlangan + bloklangan).
    """
    rows = (
        db.query(Cluster, User, District)
        .join(User, User.cluster_id == Cluster.id)
        .join(District, District.code == Cluster.district_code, isouter=True)
        .filter(Cluster.status.in_(["approved", "blocked"]))
        .all()
    )

    result = []
    for cluster, user, district in rows:
        result.append({
            "id": cluster.id,
            "cluster_name": cluster.name,
            "district_code": cluster.district_code,
            "district_name": district.name if district else None,
            "cluster_type": cluster.cluster_type,
            "leader_name": cluster.leader_name,
            "leader_phone": cluster.leader_phone,
            "status": cluster.status,
            "is_active": bool(getattr(cluster, "is_active", False)),
            "created_at": getattr(cluster, "created_at", None).isoformat()
                if getattr(cluster, "created_at", None) else None,
            "username": user.username,
        })
    return result


@app.post("/api/admin/cluster-block", dependencies=[Depends(get_admin_user)])
def block_cluster(req: BlockRequest, db: Session = Depends(get_db)):
    """
    Klasterni login qilishdan cheklash yoki cheklovni olib tashlash.
    blocked=True  -> bloklash (is_active=False, status='blocked')
    blocked=False -> blokdan chiqarish (is_active=True, status='approved')
    """
    cluster = db.query(Cluster).filter(Cluster.id == req.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Klaster topilmadi.")

    if req.blocked:
        cluster.is_active = False
        cluster.status = "blocked"
    else:
        cluster.is_active = True
        # agar avval approved bo‘lgan bo‘lsa shu holatga qaytaramiz
        if cluster.status == "blocked":
            cluster.status = "approved"

    db.commit()
    return {"message": "Holat yangilandi."}


@app.delete("/api/admin/cluster/{cluster_id}", dependencies=[Depends(get_admin_user)])
def delete_cluster(cluster_id: int, db: Session = Depends(get_db)):
    """
    Klasterni bazadan butunlay o'chirish.
    Klasterga biriktirilgan user va barcha hisobotlar ham o'chiriladi.
    """
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Klaster topilmadi.")

    # hisobotlarni o'chiramiz
    db.query(ClusterReport).filter(ClusterReport.cluster_id == cluster_id).delete()
    # foydalanuvchini o'chiramiz
    db.query(User).filter(User.cluster_id == cluster_id).delete()

    db.delete(cluster)
    db.commit()
    return {"message": "Klaster va unga tegishli ma'lumotlar o'chirildi."}

# ============================================================
#  Root
# ============================================================

@app.get("/")
def root():
    return {"message": "Qashqadaryo agroklaster backend ishlamoqda."}
