import asyncio
from datetime import datetime
import base64
import io
import json
import os
import socket
import time
import threading
import customtkinter as ctk
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tkinter import filedialog
from PIL import Image
import websockets

# Próba zaimportowania PyAudio do rozmów głosowych
try:
    import pyaudio
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

ctk.set_appearance_mode("dark")


class TelegramGroupTopSep(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Topsep — Telegram Groups & Voice")
        self.geometry("950x700")
        self.configure(fg_color="#0E1621")

        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")

        self.my_nickname = "Anonim"
        self.room_name = "ogolny"
        self.room_key = None
        self.ws_connection = None

        # Voice Chat state
        self.is_in_voice = False
        self.audio_stream_in = None
        self.audio_stream_out = None
        self.udp_sock = None

        self.last_msg_time = 0
        self.SPAM_COOLDOWN = 0.4

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.setup_sidebar()
        self.setup_chat_area()

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_async_loop, daemon=True).start()

    def _start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _derive_key(self, passphrase: str) -> bytes:
        # Generowanie stałego klucza AES-256 z nazwy/hasła pokoju
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"topsep_salt_2026",
            iterations=100_000,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=270, corner_radius=0, fg_color="#17212B"
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1)

        # Logo
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="Topsep",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#64B5F6",
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 2), sticky="w")

        # Twój Nick
        self.nick_label = ctk.CTkLabel(
            self.sidebar,
            text="TWÓJ NICK",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#6C7883",
        )
        self.nick_label.grid(row=1, column=0, padx=20, pady=(10, 2), sticky="w")

        self.nick_entry = ctk.CTkEntry(
            self.sidebar,
            fg_color="#0E1621",
            border_color="#242F3D",
            text_color="#F5F5F5",
            height=34,
            corner_radius=8,
        )
        self.nick_entry.insert(0, "Anonim")
        self.nick_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Nazwa Grupy / Pokoju
        self.room_label = ctk.CTkLabel(
            self.sidebar,
            text="NAZWA POKOJU / HASŁO GRUPY",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#6C7883",
        )
        self.room_label.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")

        self.room_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="np. KukiMafia",
            fg_color="#0E1621",
            border_color="#242F3D",
            text_color="#F5F5F5",
            height=34,
            corner_radius=8,
        )
        self.room_entry.insert(0, "KukiMafia")
        self.room_entry.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Serwer
        self.ip_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="topsep.onrender.com",
            fg_color="#0E1621",
            border_color="#242F3D",
            text_color="#F5F5F5",
            height=34,
            corner_radius=8,
        )
        self.ip_entry.insert(0, "topsep.onrender.com")
        self.ip_entry.grid(row=5, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Przycisk połączenia
        self.conn_btn = ctk.CTkButton(
            self.sidebar,
            text="Dołącz do pokoju",
            command=self.start_connection,
            fg_color="#5288C1",
            hover_color="#4676A9",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=36,
            corner_radius=8,
        )
        self.conn_btn.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        # KANAŁ GŁOSOWY
        self.voice_btn = ctk.CTkButton(
            self.sidebar,
            text="🎤 Dołącz do rozmowy",
            command=self.toggle_voice_chat,
            fg_color="#2B5278",
            hover_color="#3B6288",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=36,
            corner_radius=8,
        )
        self.voice_btn.grid(row=7, column=0, padx=20, pady=(15, 5), sticky="ew")

        # Status
        self.status_frame = ctk.CTkFrame(
            self.sidebar, fg_color="#0E1621", corner_radius=10
        )
        self.status_frame.grid(
            row=9, column=0, padx=20, pady=(20, 20), sticky="sew"
        )

        self.status_lbl = ctk.CTkLabel(
            self.status_frame,
            text="● Offline",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#E53935",
        )
        self.status_lbl.pack(padx=12, pady=10, anchor="w")

    def setup_chat_area(self):
        self.main_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="#0E1621"
        )
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header
        self.chat_header = ctk.CTkFrame(
            self.main_frame, height=55, corner_radius=0, fg_color="#17212B"
        )
        self.chat_header.grid(row=0, column=0, sticky="ew")
        self.chat_header.grid_columnconfigure(0, weight=1)

        self.header_room_lbl = ctk.CTkLabel(
            self.chat_header,
            text="Brak pokoju",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#F5F5F5",
        )
        self.header_room_lbl.grid(row=0, column=0, padx=20, pady=(8, 0), sticky="w")

        self.header_status_lbl = ctk.CTkLabel(
            self.chat_header,
            text="Dołącz do pokoju, aby rozmawiać w grupie",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#7F91A4",
        )
        self.header_status_lbl.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        # Scroll wiadomości
        self.messages_scroll = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="#0E1621"
        )
        self.messages_scroll.grid(
            row=1, column=0, padx=10, pady=10, sticky="nsew"
        )
        self.messages_scroll.grid_columnconfigure(0, weight=1)

        # Input
        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="#17212B", height=60, corner_radius=0
        )
        self.input_frame.grid(row=2, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)

        self.file_btn = ctk.CTkButton(
            self.input_frame,
            text="📎",
            command=self.send_image,
            fg_color="transparent",
            hover_color="#242F3D",
            text_color="#7F91A4",
            font=ctk.CTkFont(size=20),
            width=45,
            height=45,
            corner_radius=22,
        )
        self.file_btn.grid(row=0, column=0, padx=(10, 5), pady=8)

        self.cmd_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Napisz wiadomość do grupy...",
            fg_color="#0E1621",
            border_width=0,
            text_color="#F5F5F5",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=40,
            corner_radius=20,
        )
        self.cmd_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_text_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="➤",
            command=self.send_text_message,
            fg_color="#5288C1",
            hover_color="#4676A9",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            width=40,
            height=40,
            corner_radius=20,
        )
        self.send_btn.grid(row=0, column=2, padx=(5, 12), pady=8)

    def add_system_message(self, text):
        lbl = ctk.CTkLabel(
            self.messages_scroll,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#6C7883",
        )
        lbl.pack(pady=4)

    def add_message_bubble(self, content, sender_nick, is_me=False, is_image=False):
        now = datetime.now().strftime("%H:%M")

        bubble_row = ctk.CTkFrame(self.messages_scroll, fg_color="transparent")
        bubble_row.pack(fill="x", pady=3, padx=10)

        bg_color = "#2B5278" if is_me else "#242F3D"
        side = "right" if is_me else "left"
        anchor = "e" if is_me else "w"

        bubble = ctk.CTkFrame(bubble_row, fg_color=bg_color, corner_radius=12)
        bubble.pack(side=side, anchor=anchor, ipadx=4, ipady=2)

        if not is_me:
            nick_lbl = ctk.CTkLabel(
                bubble,
                text=sender_nick,
                text_color="#64B5F6",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            )
            nick_lbl.pack(anchor="w", padx=10, pady=(4, 0))

        if is_image:
            try:
                img_data = base64.b64decode(content)
                pil_img = Image.open(io.BytesIO(img_data))
                pil_img.thumbnail((280, 280))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

                img_lbl = ctk.CTkLabel(bubble, image=ctk_img, text="")
                img_lbl.pack(anchor="w", padx=6, pady=(6, 2))
            except Exception:
                msg_lbl = ctk.CTkLabel(bubble, text="[Błąd obrazu]", text_color="#E53935")
                msg_lbl.pack(anchor="w", padx=10, pady=(4, 0))
        else:
            msg_lbl = ctk.CTkLabel(
                bubble,
                text=content,
                text_color="#F5F5F5",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                wraplength=420,
                justify="left",
            )
            msg_lbl.pack(anchor="w", padx=10, pady=(4, 0))

        time_lbl = ctk.CTkLabel(
            bubble,
            text=now,
            text_color="#8A9EA8" if is_me else "#7F91A4",
            font=ctk.CTkFont(family="Segoe UI", size=8),
        )
        time_lbl.pack(anchor="e", padx=8, pady=(0, 2))

    def _encrypt_room_data(self, plain_text: str) -> str:
        aesgcm = AESGCM(self.room_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        return (nonce + ciphertext).hex()

    def _decrypt_room_data(self, hex_data: str) -> str:
        try:
            raw_bytes = bytes.fromhex(hex_data)
            nonce = raw_bytes[:12]
            ciphertext = raw_bytes[12:]
            aesgcm = AESGCM(self.room_key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8")
        except Exception:
            return None  # Wiadomość z innego pokoju / niepoprawne hasło

    def start_connection(self):
        self.my_nickname = self.nick_entry.get().strip() or "Anonim"
        self.room_name = self.room_entry.get().strip() or "KukiMafia"
        self.room_key = self._derive_key(self.room_name)

        self.header_room_lbl.configure(text=f"Grupa: {self.room_name}")
        self.header_status_lbl.configure(text="Szyfrowanie AES-256 aktywne", text_color="#64B5F6")
        self.status_lbl.configure(text="● Łączenie...", text_color="#FFA726")

        domain = (
            self.ip_entry.get()
            .strip()
            .replace("https://", "")
            .replace("http://", "")
            .strip("/")
        )

        url = f"ws://{domain}" if ("127.0.0.1" in domain or "localhost" in domain) else f"wss://{domain}"
        asyncio.run_coroutine_threadsafe(self.connect_ws(url), self.loop)

    async def connect_ws(self, url):
        try:
            self.ws_connection = await websockets.connect(url, max_size=10_000_000)
            self.status_lbl.configure(text="● Połączono z grupą", text_color="#66BB6A")
            self.add_system_message(f"Dołączono do pokoju '{self.room_name}'.")

            async for raw_msg in self.ws_connection:
                if raw_msg.startswith("ROOM_MSG:"):
                    decrypted_json = self._decrypt_room_data(raw_msg[9:])
                    if decrypted_json:
                        data = json.loads(decrypted_json)
                        if data.get("sender") != self.my_nickname:
                            self.add_message_bubble(
                                content=data["content"],
                                sender_nick=data["sender"],
                                is_me=False,
                                is_image=data.get("is_image", False),
                            )
        except Exception as e:
            self.status_lbl.configure(text="● Rozłączono", text_color="#E53935")
            self.add_system_message(f"Błąd połączenia: {e}")

    def send_text_message(self):
        text = self.cmd_entry.get().strip()
        if not text or not self.ws_connection:
            return

        payload = json.dumps({"sender": self.my_nickname, "content": text, "is_image": False})
        encrypted_hex = self._encrypt_room_data(payload)

        asyncio.run_coroutine_threadsafe(
            self.ws_connection.send("ROOM_MSG:" + encrypted_hex), self.loop
        )
        self.add_message_bubble(text, sender_nick=self.my_nickname, is_me=True, is_image=False)
        self.cmd_entry.delete(0, "end")

    def send_image(self):
        if not self.ws_connection:
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("Obrazy", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        if not file_path:
            return

        with open(file_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

        payload = json.dumps({"sender": self.my_nickname, "content": b64_img, "is_image": True})
        encrypted_hex = self._encrypt_room_data(payload)

        asyncio.run_coroutine_threadsafe(
            self.ws_connection.send("ROOM_MSG:" + encrypted_hex), self.loop
        )
        self.add_message_bubble(b64_img, sender_nick=self.my_nickname, is_me=True, is_image=True)

    # --- KANAŁ GŁOSOWY ---
    def toggle_voice_chat(self):
        if not HAS_AUDIO:
            self.add_system_message("Zainstaluj PyAudio (pip install pyaudio), aby używać rozmów!")
            return

        if not self.is_in_voice:
            self.is_in_voice = True
            self.voice_btn.configure(text="🛑 Opuść rozmowę", fg_color="#E53935")
            self.add_system_message("Połączono z kanałem głosowym.")
            threading.Thread(target=self._start_audio, daemon=True).start()
        else:
            self.is_in_voice = False
            self.voice_btn.configure(text="🎤 Dołącz do rozmowy", fg_color="#2B5278")
            self.add_system_message("Opuszczono kanał głosowy.")

    def _start_audio(self):
        p = pyaudio.PyAudio()
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 20000

        try:
            self.audio_stream_in = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            self.audio_stream_out = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

            while self.is_in_voice:
                data = self.audio_stream_in.read(CHUNK, exception_on_overflow=False)
                # Dźwięk jest natychmiast odtwarzany na wyjściu (pętla odsłuchowa / streaming)
                self.audio_stream_out.write(data)
        except Exception:
            pass
        finally:
            if self.audio_stream_in:
                self.audio_stream_in.stop_stream()
                self.audio_stream_in.close()
            if self.audio_stream_out:
                self.audio_stream_out.stop_stream()
                self.audio_stream_out.close()
            p.terminate()


if __name__ == "__main__":
    app = TelegramGroupTopSep()
    app.mainloop()
