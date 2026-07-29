import asyncio
from datetime import datetime
import base64
import io
import json
import os
import time
import threading
import customtkinter as ctk
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from tkinter import filedialog
from PIL import Image
import websockets

ctk.set_appearance_mode("dark")


class TelegramStyleTopSep(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Topsep — Telegram Edition")
        self.geometry("920x680")
        self.configure(fg_color="#0E1621")  # Ciemne tło Telegrama

        # Ikona
        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")

        self.my_nickname = "Ja"
        self.peer_nickname = "Oczekuję na rozmówcę..."

        # Generowanie kluczy RSA-2048
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self.public_key = self.private_key.public_key()
        self.peer_public_key = None
        self.ws_connection = None

        # Antyspam
        self.last_msg_time = 0
        self.SPAM_COOLDOWN = 0.5  # Szybki cooldown (0.5s)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.setup_sidebar()
        self.setup_chat_area()

        # Pętla asynchroniczna w tle
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_async_loop, daemon=True).start()

    def _start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_sidebar(self):
        # Lewy panel w stylu Telegrama (#17212B)
        self.sidebar = ctk.CTkFrame(
            self, width=260, corner_radius=0, fg_color="#17212B"
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        # Nagłówek
        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="Topsep",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#64B5F6",
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 2), sticky="w")

        self.sub_logo = ctk.CTkLabel(
            self.sidebar,
            text="Secure E2EE Messenger",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#7F91A4",
        )
        self.sub_logo.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Twój Nick
        self.nick_label = ctk.CTkLabel(
            self.sidebar,
            text="TWÓJ NICK",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#6C7883",
        )
        self.nick_label.grid(row=2, column=0, padx=20, pady=(5, 2), sticky="w")

        self.nick_entry = ctk.CTkEntry(
            self.sidebar,
            fg_color="#0E1621",
            border_color="#242F3D",
            border_width=1,
            text_color="#F5F5F5",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=36,
            corner_radius=8,
        )
        self.nick_entry.insert(0, "Anonim")
        self.nick_entry.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Serwer / Domena
        self.ip_label = ctk.CTkLabel(
            self.sidebar,
            text="ADRES SERWERA",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#6C7883",
        )
        self.ip_label.grid(row=4, column=0, padx=20, pady=(5, 2), sticky="w")

        self.ip_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="topsep.onrender.com",
            fg_color="#0E1621",
            border_color="#242F3D",
            border_width=1,
            text_color="#F5F5F5",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=36,
            corner_radius=8,
        )
        self.ip_entry.insert(0, "topsep.onrender.com")
        self.ip_entry.grid(row=5, column=0, padx=20, pady=(0, 15), sticky="ew")

        # Przycisk połączenia
        self.conn_btn = ctk.CTkButton(
            self.sidebar,
            text="Połącz",
            command=self.start_connection,
            fg_color="#5288C1",
            hover_color="#4676A9",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=8,
        )
        self.conn_btn.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        # Status
        self.status_frame = ctk.CTkFrame(
            self.sidebar, fg_color="#0E1621", corner_radius=10
        )
        self.status_frame.grid(
            row=7, column=0, padx=20, pady=(20, 20), sticky="sew"
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

        # Górny Pasek Czatu (Header Telegrama)
        self.chat_header = ctk.CTkFrame(
            self.main_frame, height=55, corner_radius=0, fg_color="#17212B"
        )
        self.chat_header.grid(row=0, column=0, sticky="ew")
        self.chat_header.grid_columnconfigure(0, weight=1)

        self.header_peer_lbl = ctk.CTkLabel(
            self.chat_header,
            text="Brak aktywnej rozmowy",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#F5F5F5",
        )
        self.header_peer_lbl.grid(row=0, column=0, padx=20, pady=(8, 0), sticky="w")

        self.header_status_lbl = ctk.CTkLabel(
            self.chat_header,
            text="Połącz się z serwerem, aby zacząć",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#7F91A4",
        )
        self.header_status_lbl.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        # Obszar czatu ze skrolowaniem
        self.messages_scroll = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="#0E1621"
        )
        self.messages_scroll.grid(
            row=1, column=0, padx=10, pady=10, sticky="nsew"
        )
        self.messages_scroll.grid_columnconfigure(0, weight=1)

        # Dolny pasek wpisywania wiadomości
        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="#17212B", height=60, corner_radius=0
        )
        self.input_frame.grid(
            row=2, column=0, sticky="ew"
        )
        self.input_frame.grid_columnconfigure(1, weight=1)

        # Przycisk załącznika (Spinacz)
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

        # Pole wpisywania
        self.cmd_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Napisz wiadomość...",
            fg_color="#0E1621",
            border_width=0,
            text_color="#F5F5F5",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=40,
            corner_radius=20,
        )
        self.cmd_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_text_message())

        # Przycisk Wyślij (Samolocik / Przycisk Telegrama)
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

        self.add_system_message("Wpisz adres serwera i kliknij Połącz.")

    def add_system_message(self, text):
        lbl = ctk.CTkLabel(
            self.messages_scroll,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#6C7883",
        )
        lbl.pack(pady=6)

    def add_message_bubble(self, content, sender_nick, is_me=False, is_image=False):
        now = datetime.now().strftime("%H:%M")

        bubble_row = ctk.CTkFrame(self.messages_scroll, fg_color="transparent")
        bubble_row.pack(fill="x", pady=3, padx=10)

        # Kolory Telegrama: #2B5278 dla "Moich", #242F3D dla "Rozmówcy"
        bg_color = "#2B5278" if is_me else "#242F3D"
        side = "right" if is_me else "left"
        anchor = "e" if is_me else "w"

        bubble = ctk.CTkFrame(
            bubble_row, fg_color=bg_color, corner_radius=12
        )
        bubble.pack(side=side, anchor=anchor, ipadx=4, ipady=2)

        # Nick w bąbelku (tylko dla rozmówcy w Telegramie)
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
                msg_lbl = ctk.CTkLabel(bubble, text="[Błąd ładowania obrazu]", text_color="#E53935")
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

        # Godzina w rogu bąbelka
        time_color = "#8A9EA8" if is_me else "#7F91A4"
        time_lbl = ctk.CTkLabel(
            bubble,
            text=now,
            text_color=time_color,
            font=ctk.CTkFont(family="Segoe UI", size=8),
        )
        time_lbl.pack(anchor="e", padx=8, pady=(0, 2))

    def is_spam(self):
        current_time = time.time()
        if current_time - self.last_msg_time < self.SPAM_COOLDOWN:
            return True
        self.last_msg_time = current_time
        return False

    def start_connection(self):
        self.my_nickname = self.nick_entry.get().strip() or "Anonim"
        self.status_lbl.configure(text="● Łączenie...", text_color="#FFA726")
        domain = (
            self.ip_entry.get()
            .strip()
            .replace("https://", "")
            .replace("http://", "")
            .strip("/")
        )

        if "127.0.0.1" in domain or "localhost" in domain:
            url = f"ws://{domain}"
        else:
            url = f"wss://{domain}"

        asyncio.run_coroutine_threadsafe(self.connect_ws(url), self.loop)

    async def connect_ws(self, url):
        try:
            self.ws_connection = await websockets.connect(url, max_size=10_000_000)

            pub_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")

            handshake = json.dumps({"pem": pub_pem, "nick": self.my_nickname})
            await self.ws_connection.send("KEY:" + handshake)

            self.status_lbl.configure(text="● Połączono", text_color="#66BB6A")
            self.add_system_message("Połączono z serwerem. Oczekiwanie na drugą osobę...")

            async for raw_msg in self.ws_connection:
                if raw_msg.startswith("KEY:"):
                    try:
                        key_info = json.loads(raw_msg[4:])
                        pem_data = key_info["pem"].encode("utf-8")

                        if self.peer_public_key is None:
                            self.peer_public_key = serialization.load_pem_public_key(pem_data)
                            self.peer_nickname = key_info.get("nick", "Rozmówca")

                            # Aktualizacja paska górnego
                            self.header_peer_lbl.configure(text=self.peer_nickname)
                            self.header_status_lbl.configure(text="online", text_color="#64B5F6")

                            self.add_system_message(f"Nawiązano bezpieczne połączenie E2EE z {self.peer_nickname}.")
                            await self.ws_connection.send("KEY:" + handshake)
                    except Exception:
                        pass

                elif raw_msg.startswith("MSG:"):
                    decrypted = self._decrypt_raw(raw_msg[4:])
                    if decrypted:
                        self.add_message_bubble(decrypted, sender_nick=self.peer_nickname, is_me=False, is_image=False)

                elif raw_msg.startswith("IMG:"):
                    decrypted = self._decrypt_raw(raw_msg[4:])
                    if decrypted:
                        self.add_message_bubble(decrypted, sender_nick=self.peer_nickname, is_me=False, is_image=True)

        except Exception as e:
            self.status_lbl.configure(text="● Błąd", text_color="#E53935")
            self.add_system_message(f"Błąd połączenia: {e}")

    def _encrypt_bytes(self, data_bytes):
        chunk_size = 190
        encrypted_chunks = []
        for i in range(0, len(data_bytes), chunk_size):
            chunk = data_bytes[i:i + chunk_size]
            encrypted_chunk = self.peer_public_key.encrypt(
                chunk,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            encrypted_chunks.append(encrypted_chunk.hex())
        return "|".join(encrypted_chunks)

    def _decrypt_raw(self, raw_hex_data):
        try:
            chunks = raw_hex_data.split("|")
            decrypted_bytes = bytearray()
            for chunk_hex in chunks:
                chunk_bytes = bytes.fromhex(chunk_hex)
                decrypted_chunk = self.private_key.decrypt(
                    chunk_bytes,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None,
                    ),
                )
                decrypted_bytes.extend(decrypted_chunk)
            return decrypted_bytes.decode("utf-8")
        except Exception:
            return None

    def send_text_message(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return

        if self.peer_public_key is None:
            self.add_system_message("Czekasz na połączenie drugiej osoby...")
            return

        if self.is_spam():
            return

        try:
            hex_payload = self._encrypt_bytes(text.encode("utf-8"))
            asyncio.run_coroutine_threadsafe(
                self.ws_connection.send("MSG:" + hex_payload), self.loop
            )
            self.add_message_bubble(text, sender_nick=self.my_nickname, is_me=True, is_image=False)
            self.cmd_entry.delete(0, "end")
        except Exception as e:
            self.add_system_message(f"Błąd wysyłania: {e}")

    def send_image(self):
        if self.peer_public_key is None:
            self.add_system_message("Czekasz na połączenie drugiej osoby...")
            return

        if self.is_spam():
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("Obrazy", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()

            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            hex_payload = self._encrypt_bytes(b64_img.encode("utf-8"))

            asyncio.run_coroutine_threadsafe(
                self.ws_connection.send("IMG:" + hex_payload), self.loop
            )
            self.add_message_bubble(b64_img, sender_nick=self.my_nickname, is_me=True, is_image=True)
        except Exception as e:
            self.add_system_message(f"Błąd wysyłania zdjęcia: {e}")


if __name__ == "__main__":
    app = TelegramStyleTopSep()
    app.mainloop()
