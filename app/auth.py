from app.database import db
from typing import Optional, Tuple

def validate_login(email: str, password: str) -> Optional[dict]:
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check admin (accstatus = Active)
    cursor.execute("""
        SELECT * FROM av_master_account 
        WHERE email = %s AND accstatus = 'Active'
    """, (email,))
    admin = cursor.fetchone()
    
    if not admin:
        conn.close()
        return None
    
    # Check user (status = Active) - DEFAULT VALUES if NULL
    cursor.execute("""
        SELECT userid, email, status, 
               COALESCE(sstime, 5) as sstime, 
               COALESCE(inactivitythreshold, 30) as inactivitythreshold
        FROM av_user 
        WHERE email = %s AND status = 'Active'
    """, (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return None
    
    conn.close()
    return {
        "email": user["email"],
        "sstime": user["sstime"] * 60,  # Minutes → seconds
        "inactivitythreshold": user["inactivitythreshold"] * 60  # Minutes → seconds
    }
