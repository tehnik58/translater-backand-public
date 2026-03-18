import json
from sqlalchemy.orm import Session
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

db_router = APIRouter()

from config import settings

# Создаем файл базы данных
DATABASE_URL = settings.database_url
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    student_name = Column(String, index=True)  # Индекс для быстрого поиска
    date = Column(String)
    original_text = Column(Text)
    ai_answer = Column(Text)  # Здесь будем хранить JSON как строку

# Создаем таблицы
Base.metadata.create_all(bind=engine)

def save_or_update_analysis(db: Session, name: str, date: str, original_text: str, ai_answer: dict):
    """
    Ищет запись по имени студента и тексту. 
    Если находит — обновляет ответ, если нет — создает новую.
    """
    ai_answer_str = json.dumps(ai_answer, ensure_ascii=False)
    
    # Пытаемся найти существующую запись
    existing_record = db.query(AnalysisResult).filter(
        AnalysisResult.student_name == name,
        AnalysisResult.original_text == original_text
    ).first()

    if existing_record:
        # Обновляем
        existing_record.ai_answer = ai_answer_str
        existing_record.date = date
        return existing_record
    else:
        # Создаем новую
        new_record = AnalysisResult(
            student_name=name,
            date=date,
            original_text=original_text,
            ai_answer=ai_answer_str
        )
        db.add(new_record)
        return new_record
    
@db_router.post("/")
async def students_hierarhy():
    return {"OK":"OK"}

@db_router.get("/get_student_history/{name}")
async def get_history(name: str):
    db = SessionLocal()
    results = db.query(AnalysisResult).filter(AnalysisResult.student_name == name).all()
    db.close()
    
    return [
        {
            "date": r.date,
            "original": r.original_text,
            "answer": json.loads(r.ai_answer) # Превращаем строку обратно в объект
        } for r in results
    ]