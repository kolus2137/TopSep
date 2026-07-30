import sqlite3
import json
import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Ścieżka do bazy w katalogu /tmp dla serwerów Linux/Render
DB_PATH = "/tmp/chat.db" if os.name != "nt" else "chat.db"

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

class UserAuth(BaseModel):
    username: str
    password: str

@app.post("/register")
def register(user: UserAuth):
    username_clean = user.username.strip()
    if not username_clean or not user.password:
        raise HTTPException(status_code=400, detail="Uzupełnij nick i hasło!")

    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Sprawdzenie czy użytkownik faktycznie istnieje w bazie
    try:
        cursor.execute("SELECT username FROM users WHERE LOWER(username) = LOWER(?)", (username_clean,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            raise HTTPException(status_code=400, detail="Ten nick jest już zajęty!")
            
        hashed_pwd = pwd_context.hash(user.password)
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username_clean, hashed_pwd))
        conn.commit()
    except HTTPException as e:
        raise e
    except Exception as e:
        conn.close()
        # Zwracamy DOKŁADNY treść błędu z bazy
        raise HTTPException(status_code=500, detail=f"Błąd bazy: {str(e)}")
        
    conn.close()
    return {"status": "ok", "message": "Zarejestrowano pomyślnie"}

@app.post("/login")
def login(user: UserAuth):
    username_clean = user.username.strip()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT username, password_hash FROM users WHERE LOWER(username) = LOWER(?)", (username_clean,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(user.password, row[1]):
        raise HTTPException(status_code=400, detail="Zły login lub hasło!")
    
    return {"status": "ok", "username": row[0]}

@app.get("/history/{user1}/{user2}")
def get_history(user1: str, user2: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender, recipient, content, timestamp FROM messages 
        WHERE (LOWER(sender) = LOWER(?) AND LOWER(recipient) = LOWER(?)) 
           OR (LOWER(sender) = LOWER(?) AND LOWER(recipient) = LOWER(?))
        ORDER BY timestamp ASC
    """, (user1, user2, user2, user1))
    rows = cursor.fetchall()
    conn.close()
    
    return {"history": [{"sender": r[0], "recipient": r[1], "content": r[2], "timestamp": r[3]} for r in rows]}

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username.lower()] = websocket

    def disconnect(self, username: str):
        u = username.lower()
        if u in self.active_connections:
            del self.active_connections[u]

    async def send_private_message(self, sender: str, recipient: str, content: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (sender, recipient, content) VALUES (?, ?, ?)", (sender, recipient, content))
        conn.commit()
        conn.close()

        rec_key = recipient.lower()
        if rec_key in self.active_connections:
            try:
                await self.active_connections[rec_key].send_text(json.dumps({"sender": sender, "content": content}))
            except Exception:
                self.disconnect(rec_key)

manager = ConnectionManager()

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            if "recipient" in data and "content" in data:
                await manager.send_private_message(username, data["recipient"], data["content"])
    except WebSocketDisconnect:
        manager.disconnect(username)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
