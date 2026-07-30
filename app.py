import sqlite3
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- BAZA DANYCH ---
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
    # Tabela wiadomości (zapisuje zaszyfrowaną treść)
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

# --- MODEL REJESTRACJI / LOGOWANIA ---
class UserAuth(BaseModel):
    username: str
    password: str

@app.post("/register")
def register(user: UserAuth):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    hashed_pwd = pwd_context.hash(user.password)
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (user.username, hashed_pwd))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Użytkownik już istnieje")
    conn.close()
    return {"status": "ok", "message": "Zarejestrowano pomyślnie"}

@app.post("/login")
def login(user: UserAuth):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?", (user.username,))
    row = cursor.fetchone()
    conn.close()
    
    if not row or not pwd_context.verify(user.password, row[0]):
        raise HTTPException(status_code=400, detail="Błędny login lub hasło")
    
    return {"status": "ok", "username": user.username}

@app.get("/history/{user1}/{user2}")
def get_history(user1: str, user2: str):
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender, recipient, content, timestamp FROM messages 
        WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
        ORDER BY timestamp ASC
    """, (user1, user2, user2, user1))
    rows = cursor.fetchall()
    conn.close()
    
    history = [{"sender": r[0], "recipient": r[1], "content": r[2], "timestamp": r[3]} for r in rows]
    return {"history": history}

# --- OBSŁUGA WEBSOCKET ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def send_private_message(self, sender: str, recipient: str, content: str):
        # Zapisz do bazy danych
        conn = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (sender, recipient, content) VALUES (?, ?, ?)", (sender, recipient, content))
        conn.commit()
        conn.close()

        # Prześlij do odbiorcy, jeśli jest online
        data = json.dumps({"sender": sender, "content": content})
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_text(data)

manager = ConnectionManager()

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(username, websocket)
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            # data = {"recipient": "kuki", "content": "zaszyfrowana_tresc"}
            await manager.send_private_message(username, data["recipient"], data["content"])
    except WebSocketDisconnect:
        manager.disconnect(username)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
