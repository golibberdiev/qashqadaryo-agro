# models.py ichida muhim qismlar

from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)

    clusters = relationship("Cluster", back_populates="district_obj")


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, index=True)

    # asosiy ma'lumotlar
    name = Column(String, nullable=False)
    district_code = Column(String, ForeignKey("districts.code"), nullable=False)
    cluster_type = Column(String, nullable=True)

    # rahbar ma'lumotlari
    leader_name = Column(String, nullable=True)
    leader_phone = Column(String, nullable=True)

    # admin nazorati uchun
    status = Column(String, default="pending")       # pending / approved / rejected
    admin_comment = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)

    # bog'lanishlar
    district_obj = relationship("District", back_populates="clusters")

    reports = relationship("ClusterReport", back_populates="cluster")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="cluster")  # "cluster" yoki "admin"
    cluster_id = Column(Integer, ForeignKey("clusters.id"), nullable=True)

    cluster = relationship("Cluster")


class ClusterReport(Base):
    __tablename__ = "cluster_reports"

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id"), nullable=False)
    year = Column(Integer, nullable=False)

    production = Column(Float, default=0)
    export = Column(Float, default=0)
    employment = Column(Integer, default=0)
    profitability = Column(Float, default=0)

    cluster = relationship("Cluster", back_populates="reports")
