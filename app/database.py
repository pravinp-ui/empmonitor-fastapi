import mysql.connector
import os
from dotenv import load_dotenv
from typing import Optional

TABLE_PREFIX = "u968537179_"

load_dotenv()

class Database:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "ticketing-db.mysql.database.azure.com")
        self.user = os.getenv("DB_USER", "empmonitor")
        self.password = os.getenv("DB_PASSWORD", "Alticor#1001")
        self.database = os.getenv("DB_NAME", "empmonitor-db")
    
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
