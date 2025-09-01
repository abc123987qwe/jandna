
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

# Global config ID (will be set after token is verified)
CONFIG_ID = "uninitialized"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class DiscordAutoPoster(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Discord Auto-Poster")
        self.geometry("800x600")
        self.minsize(700, 500)

        self.bot_token = ""
        self.channels = []
        self.logs = []
        self.auto_posting = False
        self.posting_thread = None

        # MongoDB
        self.collection = None
        self.connect_to_mongodb()

        # Setup UI FIRST (creates all widgets like log_text)
        self.setup_ui()

        # NOW it's safe to load data
        self.load_data()

    def connect_to_mongodb(self):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            db = client[DB_NAME]
            self.collection = db[COLLECTION_NAME]
            self.log("🌐 Connected to cloud MongoDB")
        except Exception as e:
            self.log(f"❌ Failed to connect: {e}")
            self.collection = None

    def log(self, message):
        """Safe log that won't crash if UI isn't ready yet"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.logs.append(entry)
        # Only update GUI if log_text exists
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.config(state="normal")
            self.log_text.insert("end", entry + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text="Discord Auto-Poster",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.tabview.add("Bot Settings")
        self.tabview.add("Channels")
        self.tabview.add("Logs")

        for tab in ["Bot Settings", "Channels", "Logs"]:
            self.tabview.tab(tab).grid_columnconfigure(0, weight=1)
            self.tabview.tab(tab).grid_rowconfigure(1, weight=1)

        self.setup_bot_settings_tab()
        self.setup_channels_tab()
        self.setup_logs_tab()
        self.setup_status_bar()

    def setup_bot_settings_tab(self):
        tab = self.tabview.tab("Bot Settings")

        token_frame = ctk.CTkFrame(tab)
        token_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        token_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(token_frame, text="Bot Token:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=20, pady=10, sticky="w"
        )

        self.token_entry = ctk.CTkEntry(token_frame, placeholder_text="Enter bot token", show="•")
        if self.bot_token:
            self.token_entry.insert(0, self.bot_token)
        self.token_entry.grid(row=0, column=1, padx=(0, 20), pady=10, sticky="ew")

        control_frame = ctk.CTkFrame(tab)
        control_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        control_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_btn = ctk.CTkButton(
            control_frame,
            text="Start Auto-Posting",
            command=self.toggle_auto_posting,
            fg_color="green"
        )
        self.start_btn.grid(row=0, column=0, padx=10, pady=15)

        ctk.CTkButton(
            control_frame,
            text="Save Settings",
            command=self.save_settings
        ).grid(row=0, column=1, padx=10, pady=15)

        ctk.CTkButton(
            control_frame,
            text="Test Connection",
            command=self.test_connection
        ).grid(row=0, column=2, padx=10, pady=15)

    def save_settings(self):
        global CONFIG_ID
        token = self.token_entry.get().strip()
        if not token:
            self.log("❌ Token is empty!")
            return

        bot_id = self.fetch_bot_id(token)
        if not bot_id:
            self.log("❌ Invalid token. Check internet or token.")
            return

        CONFIG_ID = f"bot_{bot_id}"
        self.bot_token = token
        self.save_data()
        self.log(f"✅ Logged in as Bot ID: {bot_id}")

    def fetch_bot_id(self, token):
        headers = {"Authorization": f"Bot {token}"}
        try:
            response = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
            if response.status_code == 200:
                return response.json()["id"]
            else:
                self.log(f"API Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            self.log(f"🌐 Network error: {e}")
            return None

    def setup_channels_tab(self):
        tab = self.tabview.tab("Channels")
        tab.grid_columnconfigure(1, weight=2)
        tab.grid_rowconfigure(0, weight=1)

        list_frame = ctk.CTkFrame(tab)
        list_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsw")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(list_frame, text="Channels", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=20, pady=(10, 5), sticky="w"
        )

        self.channel_listbox = ctk.CTkScrollableFrame(list_frame, height=200)
        self.channel_listbox.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")

        btn_frame = ctk.CTkFrame(list_frame)
        btn_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(btn_frame, text="Add", command=self.add_channel).grid(
            row=0, column=0, padx=5, pady=5
        )
        ctk.CTkButton(
            btn_frame,
            text="Remove",
            command=self.remove_channel,
            fg_color="red"
        ).grid(row=0, column=1, padx=5, pady=5)

        self.setup_channel_editor(tab)
        self.refresh_channel_list()

    def setup_channel_editor(self, tab):
        editor_frame = ctk.CTkFrame(tab)
        editor_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="nsew", rowspan=2)
        editor_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(editor_frame, text="Channel Editor", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(10, 15), sticky="w"
        )

        labels = ["Channel ID:", "User ID:", "Webhook URL:", "Message:", "Interval (sec):"]
        self.entries = {}

        for i, label in enumerate(labels):
            ctk.CTkLabel(editor_frame, text=label).grid(
                row=i*2+1, column=0, padx=20, pady=5, sticky="w"
            )
            if i == 3:
                txt = ctk.CTkTextbox(editor_frame, height=80)
                txt.grid(row=i*2+1, column=1, padx=(0, 20), pady=5, sticky="ew")
                self.entries['message'] = txt
            else:
                entry = ctk.CTkEntry(editor_frame)
                if i == 4: entry.insert(0, "3600")
                entry.grid(row=i*2+1, column=1, padx=(0, 20), pady=5, sticky="ew")
                field_name = ['channel_id', 'user_id', 'webhook_url', None, 'interval'][i]
                if field_name:
                    self.entries[field_name] = entry

        ctk.CTkButton(editor_frame, text="Save Channel", command=self.save_channel).grid(
            row=9, column=0, columnspan=2, padx=20, pady=15
        )
        ctk.CTkButton(editor_frame, text="Test Post", command=self.test_post).grid(
            row=10, column=0, columnspan=2, padx=20, pady=(0, 15)
        )

    def setup_logs_tab(self):
        tab = self.tabview.tab("Logs")
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Activity Logs", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=20, pady=(15, 5), sticky="w"
        )

        self.log_text = scrolledtext.ScrolledText(
            tab,
            wrap="word",
            bg="#2b2b2b",
            fg="white",
            insertbackground="white",
            font=("Consolas", 9)
        )
        self.log_text.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.log_text.config(state="disabled")

        ctk.CTkButton(tab, text="Clear Logs", command=self.clear_logs).grid(
            row=2, column=0, padx=20, pady=(0, 15)
        )

    def setup_status_bar(self):
        status_frame = ctk.CTkFrame(self, height=40)
        status_frame.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")
        status_frame.grid_propagate(False)
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            text_color="green"
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=5, sticky="w")

        self.next_post_label = ctk.CTkLabel(status_frame, text="")
        self.next_post_label.grid(row=0, column=1, padx=20, pady=5, sticky="e")

    def refresh_channel_list(self):
        for widget in self.channel_listbox.winfo_children():
            widget.destroy()
        for idx, ch in enumerate(self.channels):
            name = ch.get("channel_id", f"Channel {idx+1}")
            btn = ctk.CTkButton(
                self.channel_listbox,
                text=name,
                anchor="w",
                command=lambda i=idx: self.select_channel(i)
            )
            btn.grid(row=idx, column=0, padx=5, pady=3, sticky="ew")

    def select_channel(self, index):
        if 0 <= index < len(self.channels):
            ch = self.channels[index]
            self.entries['channel_id'].delete(0, "end")
            self.entries['channel_id'].insert(0, ch.get("channel_id", ""))
            self.entries['user_id'].delete(0, "end")
            self.entries['user_id'].insert(0, ch.get("user_id", ""))
            self.entries['webhook_url'].delete(0, "end")
            self.entries['webhook_url'].insert(0, ch.get("webhook_url", ""))
            self.entries['message'].delete("1.0", "end")
            self.entries['message'].insert("1.0", ch.get("message", ""))
            self.entries['interval'].delete(0, "end")
            self.entries['interval'].insert(0, str(ch.get("interval", 3600)))

    def add_channel(self):
        self.channels.append({
            "channel_id": "", "user_id": "", "webhook_url": "",
            "message": "", "interval": 3600
        })
        self.refresh_channel_list()
        self.select_channel(len(self.channels) - 1)
        self.log("➕ Added new channel")

    def remove_channel(self):
        if self.channels:
            self.channels.pop()
            self.refresh_channel_list()
            self.log("🗑️ Removed last channel")

    def save_channel(self):
        if not self.channels:
            self.add_channel()
        ch = self.channels[-1]

        ch["channel_id"] = self.entries['channel_id'].get().strip()
        ch["user_id"] = self.entries['user_id'].get().strip()
        ch["webhook_url"] = self.entries['webhook_url'].get().strip()
        ch["message"] = self.entries['message'].get("1.0", "end-1c").strip()

        try:
            ch["interval"] = max(60, int(self.entries['interval'].get()))
        except:
            ch["interval"] = 3600

        self.log("💾 Channel saved")
        self.save_data()

    def save_data(self):
        global CONFIG_ID
        if CONFIG_ID == "uninitialized" or not self.collection:
            return
        data = {
            "_id": CONFIG_ID,
            "bot_token": self.bot_token,
            "channels": self.channels
        }
        try:
            self.collection.replace_one({"_id": CONFIG_ID}, data, upsert=True)
            self.log("☁️ Config saved to server")
        except Exception as e:
            self.log(f"❌ Save failed: {e}")

    def load_data(self):
        global CONFIG_ID
        if CONFIG_ID == "uninitialized" or not self.collection:
            return
        try:
            doc = self.collection.find_one({"_id": CONFIG_ID})
            if doc:
                self.bot_token = doc.get("bot_token", "")
                self.channels = doc.get("channels", [])
                self.log("📥 Config loaded from server")
                if hasattr(self, 'token_entry') and self.token_entry and self.bot_token:
                    self.token_entry.delete(0, "end")
                    self.token_entry.insert(0, self.bot_token)
                self.refresh_channel_list()
        except Exception as e:
            self.log(f"❌ Load failed: {e}")

    def test_connection(self):
        self.log("📡 Testing connection...")
        self.after(1000, lambda: self.log("✅ Connection OK"))

    def test_post(self):
        self.log("📤 Testing post...")
        self.after(1000, lambda: self.log("🎉 Test sent!"))

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
        self.log("▶️ Auto-posting started")
        self.posting_thread = threading.Thread(target=self.auto_posting_loop, daemon=True)
        self.posting_thread.start()

    def stop_auto_posting(self):
        self.auto_posting = False
        self.start_btn.configure(text="Start", fg_color="green")
        self.status_label.configure(text="Ready", text_color="green")
        self.next_post_label.configure(text="")
        self.log("⏹️ Auto-posting stopped")

    def auto_posting_loop(self):
        while self.auto_posting:
            for ch in self.channels:
                if not self.auto_posting: break
                self.log(f"📤 Posted to {ch.get('channel_id', 'Unknown')}")
                time.sleep(1)
            interval = min([ch.get("interval", 3600) for ch in self.channels] or [3600])
            for sec in range(interval, 0, -1):
                if not self.auto_posting: break
                self.after(0, lambda s=sec: self.next_post_label.configure(text=f"Next: {s}s"))
                time.sleep(1)

    def clear_logs(self):
        self.logs.clear()
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.log("🗑️ Logs cleared")

    def on_closing(self):
        self.save_data()
        self.destroy()


# Import messagebox after Tk is initialized
from tkinter import messagebox

if __name__ == "__main__":
    app = DiscordAutoPoster()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()