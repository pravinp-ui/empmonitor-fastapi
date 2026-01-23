import requests

resp = requests.post("http://localhost:8000/login", 
                    json={"email": "p.patne@alticormedia.com", "password": "Alticor@123"})
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")

input("Press Enter to exit...")
