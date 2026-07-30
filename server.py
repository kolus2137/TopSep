import sqlite3
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- INICJALIZACJA BAZY DANYCH ---
def init_db():
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    
    # Tabela użytkowników
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    
    # Tabela wiadomości
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

# --- MODELE DANYCH ---
class UserAuth(BaseModel):
    username: str
    password: str

# --- ENDPOINTY REST API ---

@app.post("/register")
def register(user: UserAuth):
    username_clean = user.username.strip()
    if not username_clean or not user.password:
        raise HTTPException(status_code=400, detail="Nazwa użytkownika i hasło nie mogą być puste.")

    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    
    # Sprawdzenie czy użytkownik już istnieje
    cursor.execute("SELECT username FROM users WHERE LOWER(username) = LOWER(?)", (username_clean,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        conn.close()
        raise HTTPException(status_code=400, detail="Użytkownik o takiej nazwie już istnieje!")
    
    try:
        hashed_pwd = pwd_context.hash(user.password)
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username_clean, hashed_pwd))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Błąd zapisu do bazy: {str(e)}")
        
    conn.close()
    return {"status": "ok", "message": "Zarejestrowano pomyślnie"}

@app.post("/login")
def login(user: UserAuth):
    username_clean = user.username.strip()
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT username, password_hash FROM users WHERE LOWER(username) = LOWER(?)", (username_clean,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(user.password, row[1]):
        raise HTTPException(status_code=400, detail="Nieprawidłowa nazwa użytkownika lub hasło.")
    
    return {"status": "ok", "username": row[0]}

@app.get("/history/{user1}/{user2}")
def get_history(user1: str, user2: str):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender, recipient, content, timestamp FROM messages 
        WHERE (LOWER(sender) = LOWER(?) AND LOWER(recipient) = LOWER(?)) 
           OR (LOWER(sender) = LOWER(?) AND LOWER(recipient) = LOWER(?))
        ORDER BY timestamp ASC
    """, (user1, user2, user2, user1))
    rows = cursor.fetchall()
    conn.close()
    
    history = [
        {
            "sender": r[0],
            "recipient": r[1],
            "content": r[2],
            "timestamp": r[3]
        } for r in rows
    ]
    return {"history": history}

# --- OBSŁUGA WEBSOCKET ---

class ConnectionManager:
    def __init__(self):
        # Słownik aktywnych połączeń: {username: WebSocket}
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username.lower()] = websocket

    def disconnect(self, username: str):
        user_key = username.lower()
        if user_key in self.active_connections:
            del self.active_connections[user_key]

    async def send_private_message(self, sender: str, recipient: str, content: str):
        # 1. Zapis do bazy danych
        conn = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (sender, recipient, content) VALUES (?, ?, ?)",
            (sender, recipient, content)
        )
        conn.commit()
        conn.close()

        # 2. Przesłanie do odbiorcy (jeśli jest połączony online)
        recipient_key = recipient.lower()
        data = json.dumps({"sender": sender, "content": content})
        if recipient_key in self.active_connections:
            try:
                await self.active_connections[recipient_key].send_text(data)
            except Exception:
                self.disconnect(recipient_key)

manager = ConnectionManager()

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            # data oczekiwana z klienta: {"recipient": "kuki", "content": "siemanko"}
            if "recipient" in data and "content" in data:
                await manager.send_private_message(username, data["recipient"], data["content"])
    except WebSocketDisconnect:
        manager.disconnect(username)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
