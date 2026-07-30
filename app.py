import asyncio
from datetime import datetime
import base64
import io
import json
import os
import threading
import customtkinter as ctk
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tkinter import filedialog
from PIL import Image
import websockets

ctk.set_appearance_mode("dark")

class ModernTopsepApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Topsep — Voice & Chat")
        self.geometry("1000x720")
        self.minsize(850, 600)
        self.configure(fg_color="#0F1117")  # Głęboki ciemny motyw

        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")

        self.my_nickname = "Anonim"
        self.room_name = "KukiMafia"
        self.room_key = None
        self.ws_connection = None

        # Voice Chat state
        self.is_in_voice = False

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
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"topsep_salt_2026",
            iterations=100_000,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def setup_sidebar(self):
        # Sidebar Container
        self.sidebar = ctk.CTkFrame(
            self, width=280, corner_radius=0, fg_color="#161922"
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        # Header / Brand
        self.brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.brand_frame.grid(row=0, column=0, padx=20, pady=(20, 15), sticky="ew")

        self.logo_label = ctk.CTkLabel(
            self.brand_frame,
            text="⚡ TOPSEP",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#5865F2",
        )
        self.logo_label.pack(side="left")

        # Nick entry section
        self.nick_lbl = ctk.CTkLabel(
            self.sidebar,
            text="NICKNAME",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#72767D",
        )
        self.nick_lbl.grid(row=1, column=0, padx=20, pady=(5, 2), sticky="w")

        self.nick_entry = ctk.CTkEntry(
            self.sidebar,
            fg_color="#1E222D",
            border_color="#2B2F3A",
            text_color="#FFFFFF",
            height=36,
            corner_radius=8,
        )
        self.nick_entry.insert(0, "Anonim")
        self.nick_entry.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="ew")

        # Room / Group entry section
        self.room_lbl = ctk.CTkLabel(
            self.sidebar,
            text="NAZWA POKOJU / KLUCZ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#72767D",
        )
        self.room_lbl.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")

        self.room_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="np. KukiMafia",
            fg_color="#1E222D",
            border_color="#2B2F3A",
            text_color="#FFFFFF",
            height=36,
            corner_radius=8,
        )
        self.room_entry.insert(0, "KukiMafia")
        self.room_entry.grid(row=4, column=0, padx=20, pady=(0, 12), sticky="ew")

        # Server Host
        self.ip_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="topsep.onrender.com",
            fg_color="#1E222D",
            border_color="#2B2F3A",
            text_color="#FFFFFF",
            height=36,
            corner_radius=8,
        )
        self.ip_entry.insert(0, "topsep.onrender.com")
        self.ip_entry.grid(row=5, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Join Server Button
        self.conn_btn = ctk.CTkButton(
            self.sidebar,
            text="Połącz z serwerem",
            command=self.start_connection,
            fg_color="#5865F2",
            hover_color="#4752C4",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=8,
        )
        self.conn_btn.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        # Voice Chat Control Section
        self.voice_box = ctk.CTkFrame(
            self.sidebar, fg_color="#1E222D", corner_radius=10
        )
        self.voice_box.grid(row=7, column=0, padx=20, pady=(20, 10), sticky="ew")

        self.voice_title = ctk.CTkLabel(
            self.voice_box,
            text="🔊 KANAŁ GŁOSOWY",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#99AAB5",
        )
        self.voice_title.pack(padx=12, pady=(10, 5), anchor="w")

        self.voice_btn = ctk.CTkButton(
            self.voice_box,
            text="🎤 Dołącz do rozmowy",
            command=self.toggle_voice_chat,
            fg_color="#2D7D46",
            hover_color="#215B32",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=34,
            corner_radius=6,
        )
        self.voice_btn.pack(padx=12, pady=(0, 10), fill="x")

        # Status Badge
        self.status_frame = ctk.CTkFrame(
            self.sidebar, fg_color="#1E222D", corner_radius=10
        )
        self.status_frame.grid(row=10, column=0, padx=20, pady=20, sticky="sew")

        self.status_lbl = ctk.CTkLabel(
            self.status_frame,
            text="● Rozłączono",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#ED4245",
        )
        self.status_lbl.pack(padx=12, pady=10, anchor="w")

    def setup_chat_area(self):
        self.main_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="#0F1117"
        )
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Top Navigation Header
        self.chat_header = ctk.CTkFrame(
            self.main_frame, height=60, corner_radius=0, fg_color="#161922"
        )
        self.chat_header.grid(row=0, column=0, sticky="ew")
        self.chat_header.grid_columnconfigure(0, weight=1)

        self.header_room_lbl = ctk.CTkLabel(
            self.chat_header,
            text="# niepołączono",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#FFFFFF",
        )
        self.header_room_lbl.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")

        self.header_status_lbl = ctk.CTkLabel(
            self.chat_header,
            text="Wpisz nazwę pokoju i połącz się, aby rozpocząć czat",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#72767D",
        )
        self.header_status_lbl.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        # Scrollable Chat Container
        self.messages_scroll = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="#0F1117"
        )
        self.messages_scroll.grid(
            row=1, column=0, padx=15, pady=10, sticky="nsew"
        )
        self.messages_scroll.grid_columnconfigure(0, weight=1)

        # Bottom Input Area
        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="#161922", height=65, corner_radius=0
        )
        self.input_frame.grid(row=2, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)

        self.file_btn = ctk.CTkButton(
            self.input_frame,
            text="➕",
            command=self.send_image,
            fg_color="#2B2F3A",
            hover_color="#3A3F4D",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            width=38,
            height=38,
            corner_radius=19,
        )
        self.file_btn.grid(row=0, column=0, padx=(15, 8), pady=12)

        self.cmd_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Napisz wiadomość...",
            fg_color="#1E222D",
            border_width=0,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=40,
            corner_radius=20,
        )
        self.cmd_entry.grid(row=0, column=1, padx=5, pady=12, sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_text_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="➤",
            command=self.send_text_message,
            fg_color="#5865F2",
            hover_color="#4752C4",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=15),
            width=40,
            height=40,
            corner_radius=20,
        )
        self.send_btn.grid(row=0, column=2, padx=(8, 15), pady=12)

    def add_system_message(self, text):
        lbl = ctk.CTkLabel(
            self.messages_scroll,
            text=f"— {text} —",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#5865F2",
        )
        lbl.pack(pady=6)

    def add_message_bubble(self, content, sender_nick, is_me=False, is_image=False):
        now = datetime.now().strftime("%H:%M")

        bubble_row = ctk.CTkFrame(self.messages_scroll, fg_color="transparent")
        bubble_row.pack(fill="x", pady=4, padx=5)

        bg_color = "#5865F2" if is_me else "#1E222D"
        side = "right" if is_me else "left"
        anchor = "e" if is_me else "w"

        bubble = ctk.CTkFrame(bubble_row, fg_color=bg_color, corner_radius=14)
        bubble.pack(side=side, anchor=anchor, ipadx=6, ipady=4)

        if not is_me:
            nick_lbl = ctk.CTkLabel(
                bubble,
                text=sender_nick,
                text_color="#00A8FC",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            )
            nick_lbl.pack(anchor="w", padx=10, pady=(4, 0))

        if is_image:
            try:
                img_data = base64.b64decode(content)
                pil_img = Image.open(io.BytesIO(img_data))
                pil_img.thumbnail((300, 300))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

                img_lbl = ctk.CTkLabel(bubble, image=ctk_img, text="")
                img_lbl.pack(anchor="w", padx=6, pady=(6, 2))
            except Exception:
                msg_lbl = ctk.CTkLabel(bubble, text="[Błąd odczytu obrazu]", text_color="#ED4245")
                msg_lbl.pack(anchor="w", padx=10, pady=(4, 0))
        else:
            msg_lbl = ctk.CTkLabel(
                bubble,
                text=content,
                text_color="#FFFFFF",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                wraplength=450,
                justify="left",
            )
            msg_lbl.pack(anchor="w", padx=10, pady=(4, 0))

        time_lbl = ctk.CTkLabel(
            bubble,
            text=now,
            text_color="#E0E3FF" if is_me else "#72767D",
            font=ctk.CTkFont(family="Segoe UI", size=9),
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
            return None

    def start_connection(self):
        self.my_nickname = self.nick_entry.get().strip() or "Anonim"
        self.room_name = self.room_entry.get().strip() or "KukiMafia"
        self.room_key = self._derive_key(self.room_name)

        self.header_room_lbl.configure(text=f"# {self.room_name}")
        self.header_status_lbl.configure(
            text="🔒 Szyfrowanie AES-256 aktywne", text_color="#57F287"
        )
        self.status_lbl.configure(text="● Łączenie...", text_color="#FEE75C")

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
            self.status_lbl.configure(text="● Połączono z serwerem", text_color="#57F287")
            self.add_system_message(f"Weszto do pokoju '{self.room_name}'")

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
            self.status_lbl.configure(text="● Rozłączono", text_color="#ED4245")
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

    # --- BEZPOŚREDNIA OBSŁUGA AUDIO (BEZ LOKALNEGO PRZESŁUCHU) ---
    def toggle_voice_chat(self):
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            self.add_system_message("Wykonaj: pip install sounddevice numpy")
            return

        if not self.is_in_voice:
            self.is_in_voice = True
            self.voice_btn.configure(text="🛑 Opuść rozmowę", fg_color="#ED4245", hover_color="#C03537")
            self.add_system_message("Mikrofon aktywny (Kanał głosowy)")
            threading.Thread(target=self._start_audio, daemon=True).start()
        else:
            self.is_in_voice = False
            self.voice_btn.configure(text="🎤 Dołącz do rozmowy", fg_color="#2D7D46", hover_color="#215B32")
            self.add_system_message("Wyłączono mikrofon")

    def _start_audio(self):
        import sounddevice as sd

        samplerate = 16000
        channels = 1

        # Callback nagrywa z mikrofonu bez przekazywania dźwięku do wyjścia głośników
        def mic_input_callback(indata, frames, time_info, status):
            if not self.is_in_voice:
                raise sd.CallbackStop()
            # Tutaj surowy bufor mic data (indata) będzie w przyszłości wysyłany siecią
            pass

        try:
            with sd.InputStream(samplerate=samplerate, channels=channels, callback=mic_input_callback):
                while self.is_in_voice:
                    sd.sleep(100)
        except Exception as e:
            self.add_system_message(f"Błąd audio: {e}")


if __name__ == "__main__":
    app = ModernTopsepApp()
    app.mainloop()
