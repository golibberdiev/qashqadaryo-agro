from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_admin_user
from models import Cluster
from schemas import ClusterAdminView

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/pending-clusters", response_model=list[ClusterAdminView])
def pending_clusters(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    return db.query(Cluster).filter(Cluster.status == "pending").all()


@router.post("/cluster-approve")
def approve_cluster(cluster_id: int, comment: str | None = None,
                    db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(404, "Klaster topilmadi")

    cluster.status = "approved"
    cluster.admin_comment = comment
    cluster.is_active = True

    db.commit()
    return {"message": "Klaster tasdiqlandi"}


@router.post("/cluster-reject")
def reject_cluster(cluster_id: int, comment: str | None = None,
                   db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(404, "Klaster topilmadi")

    cluster.status = "rejected"
    cluster.admin_comment = comment
    cluster.is_active = False

    db.commit()
    return {"message": "Klaster rad etildi"}
