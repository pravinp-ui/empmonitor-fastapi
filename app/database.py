import mysql.connector
import os
from dotenv import load_dotenv
from typing import Optional

TABLE_PREFIX = "u968537179_"

load_dotenv()

class Database:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "mysql.hostinger.com")
        self.user = os.getenv("DB_USER", "u968537179_monitor_user")
        self.password = os.getenv("Alticor@123", "")
        self.database = os.getenv("DB_NAME", "u968537179_empmonitor")
    
    def get_connection(self):
        return mysql.connector.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
            autocommit=True
        )
    
    def test_connection(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except:
            return False

db = Database()
