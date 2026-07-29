import asyncio
from datetime import datetime
import base64
import io
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


class ModernTopSep(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Topsep — Twój prywatny komunikator")
        self.geometry("880x650")
        self.configure(fg_color="#0F172A")

        # Ustawienie ikony okna
        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")

        # Generowanie kluczy RSA-2048
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self.public_key = self.private_key.public_key()
        self.peer_public_key = None
        self.ws_connection = None

        # Antyspam
        self.last_msg_time = 0
        self.SPAM_COOLDOWN = 1.0  # Wyciszenie spamu: max 1 wiadomość na sekundę

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
        self.sidebar = ctk.CTkFrame(
            self, width=240, corner_radius=0, fg_color="#1E293B"
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="Topsep",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#38BDF8",
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 2), sticky="w")

        self.sub_logo = ctk.CTkLabel(
            self.sidebar,
            text="E2EE Messenger",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8",
        )
        self.sub_logo.grid(
            row=1, column=0, padx=20, pady=(0, 25), sticky="w"
        )

        self.ip_label = ctk.CTkLabel(
            self.sidebar,
            text="SERWER / DOMENA",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B",
        )
        self.ip_label.grid(row=2, column=0, padx=20, pady=(5, 2), sticky="w")

        self.ip_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="topsep.onrender.com",
            fg_color="#0F172A",
            border_color="#334155",
            border_width=1,
            text_color="#F8FAFC",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=36,
            corner_radius=10,
        )
        self.ip_entry.insert(0, "topsep.onrender.com")
        self.ip_entry.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="ew")

        self.conn_btn = ctk.CTkButton(
            self.sidebar,
            text="Połącz z siecią",
            command=self.start_connection,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=38,
            corner_radius=10,
        )
        self.conn_btn.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.status_frame = ctk.CTkFrame(
            self.sidebar, fg_color="#0F172A", corner_radius=12
        )
        self.status_frame.grid(
            row=5, column=0, padx=20, pady=(20, 0), sticky="ew"
        )

        self.status_lbl = ctk.CTkLabel(
            self.status_frame,
            text="● Rozłączono",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#EF4444",
        )
        self.status_lbl.pack(padx=12, pady=10, anchor="w")

    def setup_chat_area(self):
        self.main_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="#0F172A"
        )
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.messages_scroll = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="transparent"
        )
        self.messages_scroll.grid(
            row=0, column=0, padx=20, pady=(15, 10), sticky="nsew"
        )
        self.messages_scroll.grid_columnconfigure(0, weight=1)

        # Dolny panel sterowania (Wpisz + Obrazek + Wyślij)
        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="transparent"
        )
        self.input_frame.grid(
            row=1, column=0, padx=20, pady=(0, 20), sticky="ew"
        )
        self.input_frame.grid_columnconfigure(1, weight=1)

        # Przycisk załącznika / zdjęcia
        self.file_btn = ctk.CTkButton(
            self.input_frame,
            text="📎",
            command=self.send_image,
            fg_color="#1E293B",
            hover_color="#334155",
            text_color="#F8FAFC",
            font=ctk.CTkFont(size=16),
            width=44,
            height=44,
            corner_radius=22,
        )
        self.file_btn.grid(row=0, column=0, padx=(0, 8))

        self.cmd_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Napisz wiadomość...",
            fg_color="#1E293B",
            border_color="#334155",
            border_width=1,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=44,
            corner_radius=22,
        )
        self.cmd_entry.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_text_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="Wyślij",
            command=self.send_text_message,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=80,
            height=44,
            corner_radius=22,
        )
        self.send_btn.grid(row=0, column=2)

        self.add_system_message("Wprowadź adres i kliknij 'Połącz z siecią'.")

    def add_system_message(self, text):
        lbl = ctk.CTkLabel(
            self.messages_scroll,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748B",
        )
        lbl.pack(pady=6)

    def add_message_bubble(self, content, is_me=False, is_image=False):
        now = datetime.now().strftime("%H:%M")

        bubble_row = ctk.CTkFrame(self.messages_scroll, fg_color="transparent")
        bubble_row.pack(fill="x", pady=4, padx=5)

        bg_color = "#2563EB" if is_me else "#334155"
        side = "right" if is_me else "left"
        anchor = "e" if is_me else "w"

        bubble = ctk.CTkFrame(
            bubble_row, fg_color=bg_color, corner_radius=16
        )
        bubble.pack(side=side, anchor=anchor, ipadx=6, ipady=2)

        if is_image:
            # Renderowanie przesłanego podglądu zdjęcia
            try:
                img_data = base64.b64decode(content)
                pil_img = Image.open(io.BytesIO(img_data))
                
                # Reskalowanie podglądu do max 250px
                pil_img.thumbnail((250, 250))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

                img_lbl = ctk.CTkLabel(bubble, image=ctk_img, text="")
                img_lbl.pack(anchor="w", padx=8, pady=(8, 0))
            except Exception as e:
                msg_lbl = ctk.CTkLabel(bubble, text="[Błąd ładowania obrazu]", text_color="#FF8888")
                msg_lbl.pack(anchor="w", padx=12, pady=(6, 0))
        else:
            msg_lbl = ctk.CTkLabel(
                bubble,
                text=content,
                text_color="#FFFFFF" if is_me else "#F8FAFC",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                wraplength=400,
                justify="left",
            )
            msg_lbl.pack(anchor="w", padx=12, pady=(6, 0))

        time_color = "#93C5FD" if is_me else "#94A3B8"
        time_lbl = ctk.CTkLabel(
            bubble,
            text=now,
            text_color=time_color,
            font=ctk.CTkFont(family="Segoe UI", size=8),
        )
        time_lbl.pack(anchor="e", padx=10, pady=(0, 4))

    def is_spam(self):
        current_time = time.time()
        if current_time - self.last_msg_time < self.SPAM_COOLDOWN:
            self.add_system_message("Wysyłasz wiadomości zbyt szybko! Zwolnij.")
            return True
        self.last_msg_time = current_time
        return False

    def start_connection(self):
        self.status_lbl.configure(
            text="● Łączenie...", text_color="#FBBF24"
        )
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
            self.ws_connection = await websockets.connect(url, max_size=10_000_000) # Większy limit pakietu na fotki

            pub_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")

            await self.ws_connection.send("KEY:" + pub_pem)

            self.status_lbl.configure(
                text="● Połączono (E2EE)", text_color="#10B981"
            )
            self.add_system_message("Połączono z węzłem sieci.")

            async for raw_msg in self.ws_connection:
                if raw_msg.startswith("KEY:"):
                    pem_data = raw_msg[4:].encode("utf-8")
                    if self.peer_public_key is None:
                        self.peer_public_key = (
                            serialization.load_pem_public_key(pem_data)
                        )
                        self.add_system_message("Wymieniono klucze. Połączenie bezpieczne.")
                        await self.ws_connection.send("KEY:" + pub_pem)

                elif raw_msg.startswith("MSG:"):
                    decrypted = self._decrypt_raw(raw_msg[4:])
                    if decrypted:
                        self.add_message_bubble(decrypted, is_me=False, is_image=False)

                elif raw_msg.startswith("IMG:"):
                    decrypted = self._decrypt_raw(raw_msg[4:])
                    if decrypted:
                        self.add_message_bubble(decrypted, is_me=False, is_image=True)

        except Exception as e:
            self.status_lbl.configure(
                text="● Błąd połączenia", text_color="#EF4444"
            )
            self.add_system_message(f"Błąd połączenia: {e}")

    def _encrypt_bytes(self, data_bytes):
        # Dzielimy dane na bloki przy wielkich plikach / RSA OAEP max block limit
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
        except Exception as e:
            return None

    def send_text_message(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return

        if self.peer_public_key is None:
            self.add_system_message("Oczekiwanie na drugiego użytkownika...")
            return

        if self.is_spam():
            return

        try:
            hex_payload = self._encrypt_bytes(text.encode("utf-8"))
            asyncio.run_coroutine_threadsafe(
                self.ws_connection.send("MSG:" + hex_payload), self.loop
            )
            self.add_message_bubble(text, is_me=True, is_image=False)
            self.cmd_entry.delete(0, "end")
        except Exception as e:
            self.add_system_message(f"Błąd wysyłania: {e}")

    def send_image(self):
        if self.peer_public_key is None:
            self.add_system_message("Oczekiwanie na drugiego użytkownika...")
            return

        if self.is_spam():
            return

        file_path = filedialog.askopenfilename(
            filetypes=[("Pliki obrazów", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
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
            self.add_message_bubble(b64_img, is_me=True, is_image=True)
        except Exception as e:
            self.add_system_message(f"Błąd wysyłania zdjęcia: {e}")


if __name__ == "__main__":
    app = ModernTopSep()
    app.mainloop()
