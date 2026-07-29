import asyncio
from datetime import datetime
import os
import threading
import customtkinter as ctk
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from PIL import Image
import websockets

ctk.set_appearance_mode("dark")


class ModernTopSep(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Topsep — Twój prywatny komunikator")
        self.geometry("850x620")
        self.configure(fg_color="#0F172A")  # Głębokie, eleganckie tło Slate

        # Ustawienie ikony okna, jeśli plik istnieje w folderze
        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")
        elif os.path.exists("icon.png"):
            img = Image.open("icon.png")
            # Domyślny sposób wspierany przez CustomTkinter / Tkinter dla png
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))

        # Generowanie kluczy RSA-2048
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self.public_key = self.private_key.public_key()
        self.peer_public_key = None
        self.ws_connection = None

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

        # Nagłówek / Logo
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

        # Adres serwera
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

        # Przycisk połącz
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

        # Pasek statusu
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

        # Obszar wiadomości (Scrollable Frame dla bąbelków)
        self.messages_scroll = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="transparent"
        )
        self.messages_scroll.grid(
            row=0, column=0, padx=20, pady=(15, 10), sticky="nsew"
        )
        self.messages_scroll.grid_columnconfigure(0, weight=1)

        # Pasek wpisywania wiadomości
        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="transparent"
        )
        self.input_frame.grid(
            row=1, column=0, padx=20, pady=(0, 20), sticky="ew"
        )
        self.input_frame.grid_columnconfigure(0, weight=1)

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
        self.cmd_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="Wyślij",
            command=self.send_message,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=90,
            height=44,
            corner_radius=22,
        )
        self.send_btn.grid(row=0, column=1)

        self.add_system_message("Wprowadź adres i kliknij 'Połącz z siecią'.")

    def add_system_message(self, text):
        lbl = ctk.CTkLabel(
            self.messages_scroll,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#64748B",
        )
        lbl.pack(pady=6)

    def add_message_bubble(self, message, is_me=False):
        now = datetime.now().strftime("%H:%M")

        # Kontener na całą linię bąbelka
        bubble_row = ctk.CTkFrame(self.messages_scroll, fg_color="transparent")
        bubble_row.pack(fill="x", pady=4, padx=5)

        if is_me:
            # Prawy bąbelek (Niebeski - Ty)
            bubble = ctk.CTkFrame(
                bubble_row, fg_color="#2563EB", corner_radius=16
            )
            bubble.pack(side="right", anchor="e", ipadx=6, ipady=2)

            msg_lbl = ctk.CTkLabel(
                bubble,
                text=message,
                text_color="#FFFFFF",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                wraplength=400,
                justify="left",
            )
            msg_lbl.pack(anchor="w", padx=12, pady=(6, 0))

            time_lbl = ctk.CTkLabel(
                bubble,
                text=now,
                text_color="#93C5FD",
                font=ctk.CTkFont(family="Segoe UI", size=8),
            )
            time_lbl.pack(anchor="e", padx=10, pady=(0, 4))
        else:
            # Lewy bąbelek (Szary - Rozmówca)
            bubble = ctk.CTkFrame(
                bubble_row, fg_color="#334155", corner_radius=16
            )
            bubble.pack(side="left", anchor="w", ipadx=6, ipady=2)

            msg_lbl = ctk.CTkLabel(
                bubble,
                text=message,
                text_color="#F8FAFC",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                wraplength=400,
                justify="left",
            )
            msg_lbl.pack(anchor="w", padx=12, pady=(6, 0))

            time_lbl = ctk.CTkLabel(
                bubble,
                text=now,
                text_color="#94A3B8",
                font=ctk.CTkFont(family="Segoe UI", size=8),
            )
            time_lbl.pack(anchor="e", padx=10, pady=(0, 4))

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
            self.ws_connection = await websockets.connect(url)

            # Wysyłamy klucz publiczny w czystym formacie tekstu PEM
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

                    # Naprawa spamu: odsyłamy klucz tylko raz, gdy jeszcze go nie mamy!
                    if self.peer_public_key is None:
                        self.peer_public_key = (
                            serialization.load_pem_public_key(pem_data)
                        )
                        self.add_system_message(
                            "Wymieniono klucze szyfrujące. Połączenie jest bezpieczne."
                        )
                        await self.ws_connection.send("KEY:" + pub_pem)

                elif raw_msg.startswith("MSG:"):
                    hex_data = raw_msg[4:]
                    encrypted_bytes = bytes.fromhex(hex_data)

                    decrypted = self.private_key.decrypt(
                        encrypted_bytes,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None,
                        ),
                    )
                    self.add_message_bubble(
                        decrypted.decode("utf-8"), is_me=False
                    )

        except Exception as e:
            self.status_lbl.configure(
                text="● Błąd połączenia", text_color="#EF4444"
            )
            self.add_system_message(f"Błąd połączenia: {e}")

    def send_message(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return

        if self.peer_public_key is None:
            self.add_system_message("Oczekiwanie na połączenie drugiego użytkownika...")
            return

        try:
            encrypted_bytes = self.peer_public_key.encrypt(
                text.encode("utf-8"),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            hex_msg = "MSG:" + encrypted_bytes.hex()

            asyncio.run_coroutine_threadsafe(
                self.ws_connection.send(hex_msg), self.loop
            )
            self.add_message_bubble(text, is_me=True)
            self.cmd_entry.delete(0, "end")
        except Exception as e:
            self.add_system_message(f"Błąd wysyłania: {e}")


if __name__ == "__main__":
    app = ModernTopSep()
    app.mainloop()
