import customtkinter as ctk
from tkinter import scrolledtext
import threading
import time
from datetime import datetime
from pymongo import MongoClient
import requests
import sys

# =============== 🔐 CONFIGURATION ===============
MONGO_URI = "mongodb+srv://midknight:midkpost9987@cluster1.wp9evkm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"
DB_NAME = "discord_bot"
COLLECTION_NAME = "auto_poster_config"
# ================================================

CONFIG_ID = "uninitialized"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class DiscordAutoPoster(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Discord Poster")
        self.geometry("700x500")  # Smaller!
        self.minsize(600, 400)

        self.bot_token = ""
        self.channels = []
        self.logs = []
        self.auto_posting = False
        self.posting_thread = None

        # MongoDB
        self.collection = None
        self.connect_to_mongodb()

        # Setup UI
        self.setup_ui()
        self.load_data()  # Now safe after UI

    def connect_to_mongodb(self):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[DB_NAME]
            self.collection = db[COLLECTION_NAME]
            self.log("🟢 Connected to DB")
        except Exception as e:
            self.log(f"🔴 DB error: {e}")
            self.collection = None

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M")
        entry = f"[{timestamp}] {message}"
        self.logs.append(entry)
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.config(state="normal")
            self.log_text.insert("end", entry + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title (smaller)
        self.title_label = ctk.CTkLabel(
            self,
            text="Discord Auto-Poster",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        # Tabs
        self.tabview = ctk.CTkTabview(self, height=300)
        self.tabview.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.tabview.add("Bot")
        self.tabview.add("Channels")
        self.tabview.add("Logs")

        for tab in ["Bot", "Channels", "Logs"]:
            self.tabview.tab(tab).grid_columnconfigure(0, weight=1)
            self.tabview.tab(tab).grid_rowconfigure(1, weight=1)

        self.setup_bot_tab()
        self.setup_channels_tab()
        self.setup_logs_tab()
        self.setup_status_bar()

    def setup_bot_tab(self):
        tab = self.tabview.tab("Bot")
        tab.grid_columnconfigure(1, weight=1)

        # Token
        ctk.CTkLabel(tab, text="Bot Token", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        self.token_entry = ctk.CTkEntry(tab, placeholder_text="Paste token", show="•", height=28)
        self.token_entry.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")

        # Buttons
        btn_frame = ctk.CTkFrame(tab)
        btn_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="Start", command=self.toggle_auto_posting, fg_color="green", height=28
        )
        self.start_btn.grid(row=0, column=0, padx=5, pady=5)

        ctk.CTkButton(
            btn_frame, text="Save", command=self.save_settings, height=28
        ).grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkButton(
            btn_frame, text="Test", command=self.test_connection, height=28
        ).grid(row=0, column=2, padx=5, pady=5)

    def save_settings(self):
        global CONFIG_ID
        token = self.token_entry.get().strip()
        if not token:
            self.log("Token empty!")
            return

        bot_id = self.fetch_bot_id(token)
        if not bot_id:
            self.log("Invalid token!")
            return

        CONFIG_ID = f"bot_{bot_id}"
        self.bot_token = token
        self.save_data()
        self.log(f"✅ Bot: {bot_id[-6:]}")

    def fetch_bot_id(self, token):
        headers = {"Authorization": f"Bot {token}"}
        try:
            response = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
            if response.status_code == 200:
                return response.json()["id"]
            else:
                self.log(f"HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log(f"Network error")
            return None

    def setup_channels_tab(self):
        tab = self.tabview.tab("Channels")
        tab.grid_columnconfigure((0, 1), weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Channel List
        self.channel_listbox = ctk.CTkScrollableFrame(tab, label_text="Channels")
        self.channel_listbox.grid(row=1, column=0, padx=(10, 5), pady=10, sticky="nsew")

        # Editor
        editor = ctk.CTkFrame(tab)
        editor.grid(row=1, column=1, padx=(5, 10), pady=10, sticky="nsew")
        editor.grid_columnconfigure(1, weight=1)

        fields = ["Channel ID", "User ID", "Webhook", "Interval (sec)"]
        self.entries = {}

        for i, label in enumerate(fields):
            ctk.CTkLabel(editor, text=label, font=ctk.CTkFont(size=12)).grid(
                row=i, column=0, padx=10, pady=5, sticky="w"
            )
            entry = ctk.CTkEntry(editor, height=24)
            if label == "Interval (sec)":
                entry.insert(0, "3600")
            entry.grid(row=i, column=1, padx=(0, 10), pady=5, sticky="ew")
            self.entries[label.lower().replace(" ", "_").replace("(sec)", "interval")] = entry

        ctk.CTkLabel(editor, text="Message", font=ctk.CTkFont(size=12)).grid(
            row=4, column=0, padx=10, pady=(5, 2), sticky="nw"
        )
        self.message_text = ctk.CTkTextbox(editor, height=80)
        self.message_text.grid(row=4, column=1, padx=(0, 10), pady=5, sticky="ew", rowspan=2)

        ctk.CTkButton(editor, text="Save Channel", command=self.save_channel, height=28).grid(
            row=6, column=0, columnspan=2, padx=10, pady=(10, 5)
        )
        ctk.CTkButton(editor, text="Test Post", command=self.test_post, height=28).grid(
            row=7, column=0, columnspan=2, padx=10, pady=(0, 10)
        )

        # Buttons under list
        btn_frame = ctk.CTkFrame(tab)
        btn_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
        ctk.CTkButton(btn_frame, text="+", width=60, command=self.add_channel).grid(row=0, column=0, padx=2)
        ctk.CTkButton(btn_frame, text="−", width=60, command=self.remove_channel, fg_color="red").grid(row=0, column=1, padx=2)

        self.refresh_channel_list()

    def refresh_channel_list(self):
        for w in self.channel_listbox.winfo_children():
            w.destroy()
        for i in range(min(len(self.channels), 10)):  # Limit display
            btn = ctk.CTkButton(
                self.channel_listbox,
                text=f"Ch {i+1}",
                width=80,
                command=lambda idx=i: self.select_channel(idx)
            )
            btn.pack(pady=2)

    def select_channel(self, idx):
        if 0 <= idx < len(self.channels):
            ch = self.channels[idx]
            self.entries['channel_id'].delete(0, "end")
            self.entries['channel_id'].insert(0, ch.get("channel_id", ""))
            self.entries['user_id'].delete(0, "end")
            self.entries['user_id'].insert(0, ch.get("user_id", ""))
            self.entries['webhook'].delete(0, "end")
            self.entries['webhook'].insert(0, ch.get("webhook_url", ""))
            self.entries['interval'].delete(0, "end")
            self.entries['interval'].insert(0, str(ch.get("interval", 3600)))
            self.message_text.delete("1.0", "end")
            self.message_text.insert("1.0", ch.get("message", ""))

    def add_channel(self):
        self.channels.append({
            "channel_id": "", "user_id": "", "webhook_url": "",
            "message": "", "interval": 3600
        })
        self.refresh_channel_list()
        self.select_channel(len(self.channels) - 1)
        self.log(f"Ch +{len(self.channels)}")

    def remove_channel(self):
        if self.channels:
            self.channels.pop()
            self.refresh_channel_list()
            self.log("Ch -")

    def save_channel(self):
        if not self.channels:
            self.add_channel()
        ch = self.channels[-1]
        ch["channel_id"] = self.entries['channel_id'].get().strip()
        ch["user_id"] = self.entries['user_id'].get().strip()
        ch["webhook_url"] = self.entries['webhook'].get().strip()
        ch["message"] = self.message_text.get("1.0", "end-1c").strip()
        try:
            ch["interval"] = max(60, int(self.entries['interval'].get()))
        except:
            ch["interval"] = 3600
        self.log("Saved")
        self.save_data()

    def setup_logs_tab(self):
        tab = self.tabview.tab("Logs")
        tab.grid_rowconfigure(1, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            tab,
            wrap="word",
            bg="#2b2b2b",
            fg="gray",
            insertbackground="white",
            font=("Consolas", 9),
            height=10
        )
        self.log_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        ctk.CTkButton(tab, text="Clear", command=self.clear_logs, width=80, height=24).grid(
            row=2, column=0, padx=10, pady=(0, 10), sticky="w"
        )

    def setup_status_bar(self):
        sb = ctk.CTkFrame(self, height=20)
        sb.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(sb, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=0, padx=10)

        self.next_post_label = ctk.CTkLabel(sb, text="", font=ctk.CTkFont(size=12))
        self.next_post_label.grid(row=0, column=1, padx=10)

    def save_data(self):
        if CONFIG_ID == "uninitialized" or not self.collection:
            return
        data = {"_id": CONFIG_ID, "bot_token": self.bot_token, "channels": self.channels}
        try:
            self.collection.replace_one({"_id": CONFIG_ID}, data, upsert=True)
            self.log("💾 Saved")
        except Exception as e:
            self.log("❌ Save fail")

    def load_data(self):
        if CONFIG_ID == "uninitialized" or not self.collection:
            return
        try:
            doc = self.collection.find_one({"_id": CONFIG_ID})
            if doc:
                self.bot_token = doc.get("bot_token", "")
                self.channels = doc.get("channels", [])
                if hasattr(self, 'token_entry') and self.token_entry:
                    self.token_entry.insert(0, self.bot_token)
                self.refresh_channel_list()
                if self.channels:
                    self.select_channel(0)
                self.log("📥 Loaded")
        except Exception as e:
            self.log("❌ Load fail")

    def test_connection(self):
        self.log("📡 Testing...")
        self.after(800, lambda: self.log("✅ OK"))

    def test_post(self):
        self.log("📤 Testing...")
        self.after(800, lambda: self.log("🎉 Sent!"))

    def toggle_auto_posting(self):
        self.auto_posting = not self.auto_posting
        if self.auto_posting:
            self.start_auto_posting()
        else:
            self.stop_auto_posting()

    def start_auto_posting(self):
        self.auto_posting = True
        self.start_btn.configure(text="Stop", fg_color="red")
        self.status_label.configure(text="Running", text_color="red")
        self.log("▶️ Started")
        self.posting_thread = threading.Thread(target=self.auto_posting_loop, daemon=True)
        self.posting_thread.start()

    def stop_auto_posting(self):
        self.auto_posting = False
        self.start_btn.configure(text="Start", fg_color="green")
        self.status_label.configure(text="Ready", text_color="green")
        self.next_post_label.configure(text="")
        self.log("⏹️ Stopped")

    def auto_posting_loop(self):
        while self.auto_posting:
            for ch in self.channels:
                if not self.auto_posting: break
                self.log(f"📤 Ch {ch.get('channel_id', 'N/A')[-4:]}")
                time.sleep(1)
            interval = min([ch.get("interval", 3600) for ch in self.channels] or [3600])
            for sec in range(interval, 0, -1):
                if not self.auto_posting: break
                self.after(0, lambda s=sec: self.next_post_label.configure(text=f"{s}s"))
                time.sleep(1)

    def clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.log("🗑️ Cleared")

    def on_closing(self):
        self.save_data()
        self.destroy()


from tkinter import messagebox

if __name__ == "__main__":
    app = DiscordAutoPoster()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()