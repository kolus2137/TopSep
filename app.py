import asyncio
from datetime import datetime
import threading
import customtkinter as ctk
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import websockets

ctk.set_appearance_mode("dark")


class DarknetTopSep(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("TOPSEP // E2EE TERMINAL")
        self.geometry("820x540")
        self.configure(fg_color="#050505")

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
        self.setup_terminal_area()

        # Uruchomienie pętli asyncio w osobnym wątku
        self.loop = asyncio.new_event_loop()
        threading.Thread(
            target=self._start_async_loop, daemon=True
        ).start()

    def _start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0, fg_color="#0a0a0a"
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self.sidebar.grid_rowconfigure(6, weight=1)

        self.logo = ctk.CTkLabel(
            self.sidebar,
            text=">_ TOPSEP",
            font=ctk.CTkFont(family="Consolas", size=22, weight="bold"),
            text_color="#00ff66",
        )
        self.logo.grid(row=0, column=0, padx=15, pady=(20, 2), sticky="w")

        self.sub_logo = ctk.CTkLabel(
            self.sidebar,
            text="ANONYMOUS E2EE RELAY",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color="#444444",
        )
        self.sub_logo.grid(row=1, column=0, padx=15, pady=(0, 20), sticky="w")

        self.ip_label = ctk.CTkLabel(
            self.sidebar,
            text="TARGET NODE DOMAIN:",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#888888",
        )
        self.ip_label.grid(row=2, column=0, padx=15, pady=(5, 2), sticky="w")

        self.ip_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="topsep.onrender.com",
            fg_color="#111111",
            border_color="#00ff66",
            border_width=1,
            text_color="#00ff66",
            font=ctk.CTkFont(family="Consolas", size=11),
            height=32,
            corner_radius=0,
        )
        self.ip_entry.insert(0, "topsep.onrender.com")
        self.ip_entry.grid(row=3, column=0, padx=15, pady=(0, 10), sticky="ew")

        self.conn_btn = ctk.CTkButton(
            self.sidebar,
            text="[ CONNECT ]",
            command=self.start_connection,
            fg_color="#00ff66",
            hover_color="#00cc52",
            text_color="#000000",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            height=32,
            corner_radius=0,
        )
        self.conn_btn.grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        self.status_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="#111111",
            border_color="#222222",
            border_width=1,
            corner_radius=0,
        )
        self.status_frame.grid(
            row=5, column=0, padx=15, pady=(20, 0), sticky="ew"
        )

        self.status_lbl = ctk.CTkLabel(
            self.status_frame,
            text="STATUS: OFFLINE",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#ff0055",
        )
        self.status_lbl.pack(padx=10, pady=8, anchor="w")

    def setup_terminal_area(self):
        self.main_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color="#050505"
        )
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.terminal = ctk.CTkTextbox(
            self.main_frame,
            fg_color="#080808",
            text_color="#00ff66",
            font=ctk.CTkFont(family="Consolas", size=12),
            activate_scrollbars=True,
            wrap="word",
            border_color="#1f1f1f",
            border_width=1,
            corner_radius=0,
        )
        self.terminal.grid(
            row=0, column=0, padx=15, pady=(15, 10), sticky="nsew"
        )

        self.input_frame = ctk.CTkFrame(
            self.main_frame, fg_color="transparent"
        )
        self.input_frame.grid(
            row=1, column=0, padx=15, pady=(0, 15), sticky="ew"
        )
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.cmd_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Wpisz wiadomość...",
            fg_color="#080808",
            border_color="#222222",
            border_width=1,
            text_color="#ffffff",
            font=ctk.CTkFont(family="Consolas", size=12),
            height=38,
            corner_radius=0,
        )
        self.cmd_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.cmd_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="SEND >",
            command=self.send_message,
            fg_color="#111111",
            hover_color="#222222",
            border_color="#00ff66",
            border_width=1,
            text_color="#00ff66",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            width=80,
            height=38,
            corner_radius=0,
        )
        self.send_btn.grid(row=0, column=1)

        self.log_sys("SYSTEM READY. ENTER NODE DOMAIN AND CONNECT.")

    def log_sys(self, text):
        now = datetime.now().strftime("%H:%M:%S")
        self.terminal.configure(state="normal")
        self.terminal.insert("end", f"[{now}] [SYS] > {text}\n")
        self.terminal.configure(state="disabled")
        self.terminal.see("end")

    def log_msg(self, sender, text, is_me=False):
        now = datetime.now().strftime("%H:%M:%S")
        self.terminal.configure(state="normal")
        tag = "YOU" if is_me else "PEER"
        self.terminal.insert("end", f"[{now}] [{tag}] > {text}\n")
        self.terminal.configure(state="disabled")
        self.terminal.see("end")

    def start_connection(self):
        self.status_lbl.configure(
            text="STATUS: CONNECTING...", text_color="#ffcc00"
        )
        domain = self.ip_entry.get().strip().replace("https://", "").replace("http://", "").strip("/")
        
        # Jeśli testujesz lokalnie, wpisz "127.0.0.1:10000", inaczej wss://
        if "127.0.0.1" in domain or "localhost" in domain:
            url = f"ws://{domain}"
        else:
            url = f"wss://{domain}"

        asyncio.run_coroutine_threadsafe(self.connect_ws(url), self.loop)

    async def connect_ws(self, url):
        try:
            self.ws_connection = await websockets.connect(url)
            
            # Wysyłamy swój klucz publiczny po połączeniu
            pub_bytes = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            await self.ws_connection.send(pub_bytes)

            self.status_lbl.configure(
                text="STATUS: ONLINE (E2EE)", text_color="#00ff66"
            )
            self.log_sys(f"CONNECTED TO NODE VIA WEBSOCKET.")

            # Pętla odbierania danych
            async for raw_data in self.ws_connection:
                if isinstance(raw_data, str):
                    raw_data = raw_data.encode("latin1")

                if self.peer_public_key is None:
                    self.peer_public_key = (
                        serialization.load_pem_public_key(raw_data)
                    )
                    self.log_sys("PEER PUBLIC KEY EXCHANGE COMPLETE. SECURE.")
                else:
                    decrypted = self.private_key.decrypt(
                        raw_data,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None,
                        ),
                    )
                    self.log_msg("PEER", decrypted.decode("utf-8"), is_me=False)

        except Exception as e:
            self.status_lbl.configure(
                text="STATUS: ERROR", text_color="#ff0055"
            )
            self.log_sys(f"CONNECTION FAILED: {e}")

    def send_message(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return

        if self.peer_public_key is None:
            self.log_sys("CANNOT SEND: WAITING FOR PEER KEY EXCHANGE...")
            return

        try:
            encrypted = self.peer_public_key.encrypt(
                text.encode("utf-8"),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            
            # Wysyłanie wiadomości przez WebSocket
            asyncio.run_coroutine_threadsafe(
                self.ws_connection.send(encrypted), self.loop
            )
            self.log_msg("YOU", text, is_me=True)
            self.cmd_entry.delete(0, "end")
        except Exception as e:
            self.log_sys(f"ENCRYPTION/SEND ERROR: {e}")


if __name__ == "__main__":
    app = DarknetTopSep()
    app.mainloop()
