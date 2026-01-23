from fastapi import APIRouter, HTTPException
from app.database import db
from datetime import datetime
from typing import Dict

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/start")
async def start_session(user_email: str, data: Dict):
    """Create new session when monitoring starts"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tblsession (user_email, start_time, status) 
        VALUES (%s, %s, 'active')
    """, (user_email, datetime.now()))
    
    session_id = cursor.lastrowid
    conn.close()
    return {"session_id": session_id}

@router.post("/end/{session_id}")
async def end_session(session_id: int, user_email: str):
    """End session properly"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE tblsession 
        SET end_time = %s, status = 'completed' 
        WHERE id = %s AND user_email = %s
    """, (datetime.now(), session_id, user_email))
    
    if cursor.rowcount == 0:
        raise HTTPException(404, "Session not found")
    
    conn.close()
    return {"status": "session_ended"}
