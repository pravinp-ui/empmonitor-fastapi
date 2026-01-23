from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import io
import os
import base64
from dotenv import load_dotenv

# Local imports
from app.database import db
from app.auth import validate_login

from fastapi.middleware.cors import CORSMiddleware
import mysql.connector

app = FastAPI(title="Employee Monitor API", version="1.0")

# Add after app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


load_dotenv()



# ------------------------------------------------------------------
# Pydantic Models
# ------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class SessionRequest(BaseModel):
    user_email: str


# ------------------------------------------------------------------
# Health & Root
# ------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "Employee Monitor API Running ✅"}


@app.get("/health")
async def health_check():
    return {
        "db_connected": db.test_connection(),
        "status": "healthy"
    }


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------

@app.post("/login")
async def login(request: LoginRequest):
    print(f"🔐 Login attempt for: {request.email}")

    user_data = validate_login(request.email, request.password)
    if not user_data:
        print(f"❌ Login failed for: {request.email}")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials or inactive account"
        )

    print(f"✅ Login SUCCESS for: {request.email}")
    return user_data


# ------------------------------------------------------------------
# Screenshot Upload
# ------------------------------------------------------------------

@app.post("/upload-screenshot")
async def upload_screenshot(
    screenshot: UploadFile = File(...),
    user_email: str = Form(...)
):
    try:
        print(f"📸 Uploading screenshot for: {user_email}")

        screenshot_bytes = await screenshot.read()

        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO u968537179_av_tblsnap (user_id, screenshot_data, capture_time)
            VALUES (%s, %s, %s)
            """,
            (user_email, screenshot_bytes, datetime.now())
        )

        screenshot_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"✅ Screenshot saved! ID: {screenshot_id}")
        return {"status": "saved", "screenshot_id": screenshot_id}

    except Exception as e:
        print(f"❌ Screenshot upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Screenshot upload failed"
        )


# ------------------------------------------------------------------
# Session Management
# ------------------------------------------------------------------

@app.post("/sessions/start")
async def start_session(request: SessionRequest):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO u968537179_tblsession (user_email, start_time, status)
            VALUES (%s, %s, 'active')
            """,
            (request.user_email, datetime.now())
        )

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"▶️ Session {session_id} started for {request.user_email}")
        return {"session_id": session_id}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to start session"
        )


@app.post("/sessions/end/{session_id}")
async def end_session(session_id: int, request: SessionRequest):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE u968537179_tblsession
            SET end_time = %s, status = 'completed'
            WHERE id = %s AND user_email = %s
            """,
            (datetime.now(), session_id, request.user_email)
        )

        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        conn.commit()
        conn.close()

        print(f"⏹️ Session {session_id} ended")
        return {"status": "ended"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to end session"
        )


# ------------------------------------------------------------------
# Screenshot Fetch
# ------------------------------------------------------------------

@app.get("/screenshot/{screenshot_id}")
async def get_screenshot(screenshot_id: int):
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT screenshot_data FROM u968537179_av_tblsnap WHERE id = %s",
        (screenshot_id,)
    )

    result = cursor.fetchone()
    conn.close()

    if not result or result[0] is None:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return StreamingResponse(
        io.BytesIO(result[0]),
        media_type="image/png"
    )


# ------------------------------------------------------------------
# Dashboard Data (GET = QUERY PARAMS, NOT FORM)
# ------------------------------------------------------------------

@app.get("/api/dashboard")
async def get_dashboard(email: str = Query(...), start_date: str = Query("2026-01-01"), end_date: str = Query("2026-01-31")):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    # JOIN av_user to get user_id from email
    cursor.execute("""
        SELECT DATE(s.start_time) as date,
               SEC_TO_TIME(SUM(TIME_TO_SEC(
                   IFNULL(TIMEDIFF(COALESCE(s.end_time, NOW()), s.start_time), 0)
               ))) as total_hours,
               COUNT(s.id) as sessions,
               SUM(TIME_TO_SEC(
                   IFNULL(TIMEDIFF(COALESCE(s.end_time, NOW()), s.start_time), 0)
               )) as total_seconds
        FROM u968537179_tblsession s
        JOIN av_user u ON s.user_email = u.email
        WHERE u.email = %s AND s.start_time BETWEEN %s AND %s AND s.status IN ('completed', 'active')
        GROUP BY DATE(s.start_time)
        ORDER BY date DESC
    """, (email, start_date, end_date))
    data = cursor.fetchall()
    conn.close()
    return {"success": True, "data": data}

# ------------------------------------------------------------------
# COMPLETE DASHBOARD API - ALL 6 METRICS
# ------------------------------------------------------------------

@app.get("/api/dashboard-summary")
async def get_dashboard_summary(email: str = Query(...)):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Total tracked time from tblsession (IST)
    cursor.execute("""
        SELECT 
            SEC_TO_TIME(SUM(TIME_TO_SEC(TIMEDIFF(COALESCE(end_time, NOW()), start_time)))) as total_tracked,
            SUM(TIME_TO_SEC(TIMEDIFF(COALESCE(end_time, NOW()), start_time))) as total_tracked_seconds
        FROM u968537179_tblsession 
        WHERE user_email = %s AND status IN ('completed', 'active')
    """, (email,))
    tracked = cursor.fetchone() or {'total_tracked_seconds': 0}
    
    # Manual time from av_manual_logs
    cursor.execute("""
        SELECT 
            SEC_TO_TIME(SUM(TIME_TO_SEC(TIMEDIFF(end_time, start_time)))) as manual_time,
            SUM(TIME_TO_SEC(TIMEDIFF(end_time, start_time))) as manual_seconds
        FROM u968537179_av_manual_logs 
        WHERE user_email = %s
    """, (email,))
    manual = cursor.fetchone() or {'manual_seconds': 0}
    
    # Inactive gaps calculation (per day first/last activity)
    cursor.execute("""
        SELECT SUM(TIME_TO_SEC(TIMEDIFF(last_activity, first_activity))) as active_per_day_seconds
        FROM (
            SELECT DATE(start_time) as day,
                   MIN(start_time) as first_activity,
                   MAX(COALESCE(end_time, NOW())) as last_activity
            FROM u968537179_tblsession 
            WHERE user_email = %s
            GROUP BY DATE(start_time)
        ) daily_activity
    """, (email,))
    active_per_day = cursor.fetchone() or {'active_per_day_seconds': 0}
    
    conn.close()
    
    total_active = tracked['total_tracked_seconds'] + manual['manual_seconds']
    
    return {
        "success": True,
        "data": {
            "username": email,
            "total_tracked": tracked['total_tracked_seconds'],
            "manual_added": manual['manual_seconds'],
            "active_time": total_active,
            "inactive_time": active_per_day['active_per_day_seconds'] * 0.2,  # 20% estimate
            "total_worked": total_active
        }
    }

# ------------------------------------------------------------------
# Screenshot Gallery
# ------------------------------------------------------------------

@app.get("/api/screenshots")
async def get_screenshots(
    email: str = Query(...),
    start_date: str = Query("2026-01-01"),
    end_date: str = Query("2026-01-31")
):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT 
        id,
        capture_time AS timestamp,
        screenshot_data
    FROM u968537179_av_tblsnap
    WHERE user_id = %s
    AND capture_time BETWEEN %s AND %s
    ORDER BY capture_time DESC
    """

    cursor.execute(query, (email, start_date, end_date))
    screenshots = cursor.fetchall()

    for shot in screenshots:
        blob = shot.pop("screenshot_data", None)

        if blob:
            shot["image_base64"] = base64.b64encode(blob).decode("utf-8")
            shot["size_kb"] = round(len(blob) / 1024, 1)
        else:
            shot["image_base64"] = None
            shot["size_kb"] = 0

        shot["timestamp_formatted"] = shot["timestamp"]

    cursor.close()
    conn.close()

    return {"success": True, "data": screenshots}




# ------------------------------------------------------------------
# # 3. DAILY TIMELINE for Manual Logs
# ------------------------------------------------------------------    

@app.get("/api/daily-timeline")
async def get_daily_timeline(email: str = Query(...), date: str = Query(None)):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    if date:
        cursor.execute("""
            SELECT 
                s.id, s.start_time, s.end_time, s.status,
                TIME_FORMAT(s.start_time, '%H:%i') as start_time_fmt,
                TIME_FORMAT(s.end_time, '%H:%i') as end_time_fmt,
                TIMESTAMPDIFF(MINUTE, s.start_time, s.end_time) as duration_min
            FROM u968537179_tblsession s
            WHERE s.user_email = %s AND DATE(s.start_time) = %s
            ORDER BY s.start_time
        """, (email, date))
    else:
        cursor.execute("""
            SELECT DISTINCT DATE(start_time) as date
            FROM u968537179_tblsession 
            WHERE user_email = %s 
            ORDER BY date DESC
        """, (email,))
    
    timeline = cursor.fetchall()
    conn.close()
    return {"success": True, "data": timeline}

# ------------------------------------------------------------------
# Manual Log (Placeholder – SAFE)
# ------------------------------------------------------------------

class ManualLogCreate(BaseModel):
    email: str
    start_time: str
    end_time: str
    notes: str = ""

@app.get("/api/manual-logs")
async def get_manual_logs(email: str = Query(...), start_date: str = Query("2026-01-01"), end_date: str = Query("2026-01-31")):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, user_email, start_time, end_time, notes, created_at
        FROM u968537179_av_manual_logs 
        WHERE user_email = %s AND DATE(start_time) BETWEEN %s AND %s
        ORDER BY start_time DESC
    """, (email, start_date, end_date))
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"success": True, "data": logs}

@app.post("/api/manual-logs")
async def create_manual_log(log: ManualLogCreate):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO u968537179_av_manual_logs (user_email, start_time, end_time, notes, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, (log.email, log.start_time, log.end_time, log.notes))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"success": True, "data": {"manual_log_id": new_id}}

@app.put("/api/manual-logs/{log_id}")
async def update_manual_log(log_id: int, log: ManualLogCreate):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE u968537179_av_manual_logs SET start_time=%s, end_time=%s, notes=%s
        WHERE id=%s AND user_email=%s
    """, (log.start_time, log.end_time, log.notes, log_id, log.email))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True, "data": {"updated_id": log_id}}

@app.delete("/api/manual-logs/{log_id}")
async def delete_manual_log(log_id: int):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM u968537179_av_manual_logs WHERE id=%s", (log_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"success": True, "data": {"deleted_id": log_id}}



# ------------------------------------------------------------------
# Profile (FIXED – NO self)
# ------------------------------------------------------------------

@app.get("/api/profile")
async def get_profile(email: str):
    return {
        "email": email,
        "settings": {}
    }


# ------------------------------------------------------------------
# Run App
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
