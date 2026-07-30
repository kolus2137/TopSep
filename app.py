import asyncio
from datetime import datetime
import json
import os
import threading
import requests
import customtkinter as ctk
from tkinter import messagebox
import websockets

ctk.set_appearance_mode("dark")

# === PODMIEŃ TE ADRESY NA SWÓJ ADRES Z RENDERA ===
SERVER_URL = "https://topsep.onrender.com"
WS_URL = "wss://topsep.onrender.com"

class TelegramApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Topsep — Messenger")
        self.geometry("950x650")
        self.minsize(800, 550)
        self.configure(fg_color="#0F1117")

        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")

        self.my_username = None
        self.active_chat_with = None
        self.ws_connection = None

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._start_async_loop, daemon=True).start()

        self.show_login_screen()

    def _start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    # --- EKRAN LOGOWANIA / REJESTRACJI ---
    def show_login_screen(self):
        self.login_frame = ctk.CTkFrame(self, fg_color="#161922", corner_radius=15)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.4, relheight=0.55)

        lbl = ctk.CTkLabel(
            self.login_frame,
            text="⚡ TOPSEP",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color="#5865F2"
        )
        lbl.pack(pady=(30, 20))

        self.user_entry = ctk.CTkEntry(
            self.login_frame,
            placeholder_text="Nazwa użytkownika",
            fg_color="#1E222D",
            border_color="#2B2F3A",
            height=40
        )
        self.user_entry.pack(padx=35, pady=8, fill="x")

        self.pass_entry = ctk.CTkEntry(
            self.login_frame,
            placeholder_text="Hasło",
            show="*",
            fg_color="#1E222D",
            border_color="#2B2F3A",
            height=40
        )
        self.pass_entry.pack(padx=35, pady=8, fill="x")

        btn_login = ctk.CTkButton(
            self.login_frame,
            text="Zaloguj się",
            command=self.handle_login,
            fg_color="#5865F2",
            hover_color="#4752C4",
            font=ctk.CTkFont(weight="bold"),
            height=40
        )
        btn_login.pack(padx=35, pady=(18, 6), fill="x")

        btn_reg = ctk.CTkButton(
            self.login_frame,
            text="Zarejestruj się",
            command=self.handle_register,
            fg_color="#2B2F3A",
            hover_color="#3A3F4D",
            height=36
        )
        btn_reg.pack(padx=35, pady=6, fill="x")

    def handle_login(self):
        u = self.user_entry.get().strip()
        p = self.pass_entry.get().strip()
        if not u or not p:
            messagebox.showwarning("Uzupełnij pola", "Podaj nazwę użytkownika oraz hasło.")
            return

        try:
            res = requests.post(f"{SERVER_URL}/login", json={"username": u, "password": p}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                self.my_username = data.get("username", u)
                self.login_frame.destroy()
                self.setup_main_ui()
                asyncio.run_coroutine_threadsafe(self.connect_ws(), self.loop)
            else:
                err_detail = res.json().get("detail", "Błąd logowania")
                messagebox.showerror("Błąd", err_detail)
        except Exception as e:
            messagebox.showerror("Błąd połączenia", f"Nie można połączyć z serwerem:\n{e}")

    def handle_register(self):
        u = self.user_entry.get().strip()
        p = self.pass_entry.get().strip()
        if not u or not p:
            messagebox.showwarning("Uzupełnij pola", "Podaj nazwę użytkownika oraz hasło.")
            return

        try:
            res = requests.post(f"{SERVER_URL}/register", json={"username": u, "password": p}, timeout=10)
            if res.status_code == 200:
                messagebox.showinfo("Sukces", "Konto zostało pomyślnie utworzone! Możesz się zalogować.")
            else:
                # Wyciąga szczegółową treść błędu prosto z FastAPI/backendu
                err_detail = res.json().get("detail", "Błąd rejestracji")
                messagebox.showerror("Błąd", err_detail)
        except Exception as e:
            messagebox.showerror("Błąd połączenia", f"Nie można połączyć z serwerem:\n{e}")

    # --- GŁÓWNY INTERFEJS CZATU ---
    def setup_main_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Lewy Panel (Lista kontaktów)
        self.sidebar = ctk.CTkFrame(self, width=280, fg_color="#161922", corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.user_title = ctk.CTkLabel(
            self.sidebar,
            text=f"👤 {self.my_username}",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#5865F2"
        )
        self.user_title.pack(padx=20, pady=(20, 15), anchor="w")

        self.search_lbl = ctk.CTkLabel(
            self.sidebar,
            text="ROZPOCZNIJ ROZMOWĘ",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#72767D"
        )
        self.search_lbl.pack(padx=20, pady=(5, 2), anchor="w")

        self.search_entry = ctk.CTkEntry(
            self.sidebar,
            placeholder_text="Wpisz nick odbiorcy i kliknij Enter...",
            fg_color="#1E222D",
            border_color="#2B2F3A",
            height=36
        )
        self.search_entry.pack(padx=15, pady=(0, 15), fill="x")
        self.search_entry.bind("<Return>", lambda e: self.open_chat_with(self.search_entry.get().strip()))

        # Prawy Panel (Wiadomości)
        self.chat_area = ctk.CTkFrame(self, fg_color="#0F1117", corner_radius=0)
        self.chat_area.grid(row=0, column=1, sticky="nsew")
        self.chat_area.grid_rowconfigure(1, weight=1)
        self.chat_area.grid_columnconfigure(0, weight=1)

        # Nagłówek
        self.header = ctk.CTkFrame(self.chat_area, height=55, fg_color="#161922", corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        
        self.header_lbl = ctk.CTkLabel(
            self.header,
            text="Wpisz nick użytkownika w panelu po lewej, aby rozpocząć rozmowę",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#FFFFFF"
        )
        self.header_lbl.pack(padx=20, pady=15, side="left")

        # Okno Wiadomości (Scrollable)
        self.messages_scroll = ctk.CTkScrollableFrame(self.chat_area, fg_color="#0F1117")
        self.messages_scroll.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")
        self.messages_scroll.grid_columnconfigure(0, weight=1)

        # Pasek wprowadzania wiadomości
        self.input_frame = ctk.CTkFrame(self.chat_area, fg_color="#161922", height=60, corner_radius=0)
        self.input_frame.grid(row=2, column=0, sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.msg_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Napisz wiadomość...",
            height=40,
            border_width=0,
            fg_color="#1E222D",
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.msg_entry.grid(row=0, column=0, padx=15, pady=12, sticky="ew")
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="➤",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="#5865F2",
            hover_color="#4752C4",
            command=self.send_message
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 15), pady=12)

    def open_chat_with(self, target_user):
        if not target_user:
            return
        if target_user.lower() == self.my_username.lower():
            messagebox.showinfo("Informacja", "Nie możesz pisać do samego siebie!")
            return

        self.active_chat_with = target_user
        self.header_lbl.configure(text=f"💬 Czat z @{target_user}")
        
        # Wyszyszczenie widoku wiadomości
        for widget in self.messages_scroll.winfo_children():
            widget.destroy()

        self.load_history(target_user)

    def load_history(self, target_user):
        try:
            res = requests.get(f"{SERVER_URL}/history/{self.my_username}/{target_user}", timeout=5)
            if res.status_code == 200:
                msgs = res.json().get("history", [])
                for m in msgs:
                    is_me = m["sender"].lower() == self.my_username.lower()
                    self.add_bubble(m["content"], is_me)
        except Exception as e:
            print("Błąd pobierania historii:", e)

    def add_bubble(self, text, is_me):
        now = datetime.now().strftime("%H:%M")
        bubble_row = ctk.CTkFrame(self.messages_scroll, fg_color="transparent")
        bubble_row.pack(fill="x", pady=4, padx=5)

        bg = "#5865F2" if is_me else "#1E222D"
        side = "right" if is_me else "left"

        bubble = ctk.CTkFrame(bubble_row, fg_color=bg, corner_radius=12)
        bubble.pack(side=side, ipadx=6, ipady=4)

        lbl = ctk.CTkLabel(
            bubble,
            text=text,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            wraplength=420,
            justify="left"
        )
        lbl.pack(padx=10, pady=(5, 1))

        time_lbl = ctk.CTkLabel(
            bubble,
            text=now,
            text_color="#E0E3FF" if is_me else "#72767D",
            font=ctk.CTkFont(family="Segoe UI", size=8)
        )
        time_lbl.pack(anchor="e", padx=8, pady=(0, 2))

    async def connect_ws(self):
        try:
            url = f"{WS_URL}/ws/{self.my_username}"
            self.ws_connection = await websockets.connect(url)
            async for raw in self.ws_connection:
                data = json.loads(raw)
                # Wyświetl natychmiast wiadomość, jeśli pisze do nas obecnie otwarty użytkownik
                sender = data.get("sender", "")
                if self.active_chat_with and sender.lower() == self.active_chat_with.lower():
                    self.add_bubble(data["content"], is_me=False)
        except Exception as e:
            print("Błąd połączenia WebSocket:", e)

    def send_message(self):
        text = self.msg_entry.get().strip()
        if not text or not self.active_chat_with or not self.ws_connection:
            return

        payload = json.dumps({"recipient": self.active_chat_with, "content": text})
        asyncio.run_coroutine_threadsafe(self.ws_connection.send(payload), self.loop)

        self.add_bubble(text, is_me=True)
        self.msg_entry.delete(0, "end")

if __name__ == "__main__":
    app = TelegramApp()
    app.mainloop()
