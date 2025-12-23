# models.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Hospital(Base):
    __tablename__ = 'hospitals'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    locality = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    website = Column(String)

class Ward(Base):
    __tablename__ = 'wards'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(Integer, ForeignKey('hospitals.id'))
    name = Column(String, nullable=False)

class Doctor(Base):
    __tablename__ = 'doctors'
    id = Column(Integer, primary_key=True)
    hospital_id = Column(Integer, ForeignKey('hospitals.id'))
    ward_id = Column(Integer, ForeignKey('wards.id'))
    name = Column(String, nullable=False)
    specialty = Column(String)
    is_available = Column(Integer, default=1)
    qualification = Column(String)
    experience_years = Column(Integer)
    email = Column(String)
    phone = Column(String)

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    doctor_id = Column(Integer, ForeignKey('doctors.id'))
    hospital_id = Column(Integer, ForeignKey('hospitals.id'))
    scheduled_at = Column(DateTime)
    status = Column(String, default='booked')
    created_at = Column(DateTime, default=datetime.utcnow)
