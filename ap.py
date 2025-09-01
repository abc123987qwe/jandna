import customtkinter as ctk
from tkinter import scrolledtext
import threading
import time
import schedule
import requests
from datetime import datetime
from pymongo import MongoClient

# =============== 🔐 YOUR MONGODB URI ===============
MONGO_URI = "mongodb+srv://midknight:midkpost9987@cluster1.wp9evkm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"
DB_NAME = "discord_bot"
COLLECTION_NAME = "auto_poster_config"
CONFIG_ID = "main_config"
# ===================================================

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class DiscordAutoPoster(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Poster")
        self.geometry("600x500")
        self.resizable(False, False)

        # Runtime
        self.start_time = datetime.now()
        self.is_running = False

        # Data
        self.token = ""
        self.webhook_url = ""
        self.channels = []  # list of dicts: {id, message, interval}
        self.current_channel_index = None

        # MongoDB
        self.collection = None
        self.connect_mongo()

        # Setup UI
        self.setup_ui()

        # Load after UI
        self.load_config()

        # Start uptime
        self.update_uptime()

    def connect_mongo(self):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[DB_NAME]
            self.collection = db[COLLECTION_NAME]
            self.log("🟢 DB: Connected")
        except Exception as e:
            self.log(f"🔴 DB: {e}")

    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}\n"
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.config(state="normal")
            self.log_text.insert("end", entry)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        else:
            print(entry.strip())

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # For tabs

        # Title
        ctk.CTkLabel(self, text="Discord Auto Poster", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=10, pady=10
        )

        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.tabview.add("Token")
        self.tabview.add("Channels")
        self.tabview.add("Logs")

        self.setup_token_tab()
        self.setup_channels_tab()
        self.setup_logs_tab()

        # === ALWAYS-VISIBLE CONTROL BAR ===
        control_frame = ctk.CTkFrame(self, height=60)
        control_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        control_frame.grid_propagate(False)
        control_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.status_label = ctk.CTkLabel(control_frame, text="Status: Stopped", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=0, padx=10, sticky="w")

        self.uptime_label = ctk.CTkLabel(control_frame, text="Uptime: 0h 0m 0s", font=ctk.CTkFont(size=12))
        self.uptime_label.grid(row=0, column=1, padx=10, sticky="e")

        self.test_btn = ctk.CTkButton(control_frame, text="Test", command=self.test_send, width=80, height=28)
        self.test_btn.grid(row=0, column=2, padx=5)

        self.start_btn = ctk.CTkButton(
            control_frame, text="Start", command=self.toggle_running,
            width=80, height=28, fg_color="green"
        )
        self.start_btn.grid(row=0, column=3, padx=5)

    def setup_token_tab(self):
        tab = self.tabview.tab("Token")
        tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Bot Token", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.token_entry = ctk.CTkEntry(tab, placeholder_text="Paste your bot token")
        self.token_entry.grid(row=0, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkLabel(tab, text="Webhook URL", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.webhook_entry = ctk.CTkEntry(tab, placeholder_text="https://discord.com/api/webhooks/...")
        self.webhook_entry.grid(row=1, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkButton(tab, text="Save Settings", command=self.save_config).grid(
            row=2, column=0, columnspan=2, padx=10, pady=10
        )

    def setup_channels_tab(self):
        tab = self.tabview.tab("Channels")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Channel List
        ctk.CTkLabel(tab, text="Channel List", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.channel_listbox = ctk.CTkScrollableFrame(tab, height=120)
        self.channel_listbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # Add/Remove Buttons
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=5)
        ctk.CTkButton(btn_frame, text="Add", command=self.add_channel, width=80).grid(row=0, column=0, padx=5)
        ctk.CTkButton(btn_frame, text="Remove", command=self.remove_channel, width=80, fg_color="red").grid(row=0, column=1, padx=5)

        # Editor
        editor = ctk.CTkFrame(tab)
        editor.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        editor.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(editor, text="Channel ID", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.ch_id_entry = ctk.CTkEntry(editor)
        self.ch_id_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")

        ctk.CTkLabel(editor, text="Message", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=5, sticky="nw")
        self.ch_msg_text = ctk.CTkTextbox(editor, height=60)
        self.ch_msg_text.grid(row=1, column=1, padx=(0,10), pady=5, sticky="ew")

        ctk.CTkLabel(editor, text="Interval (sec)", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.ch_int_entry = ctk.CTkEntry(editor)
        self.ch_int_entry.insert(0, "7200")
        self.ch_int_entry.grid(row=2, column=1, padx=(0,10), pady=5, sticky="ew")

        ctk.CTkButton(editor, text="Save Channel", command=self.save_channel).grid(
            row=3, column=0, columnspan=2, padx=10, pady=10
        )

        self.refresh_channel_list()

    def setup_logs_tab(self):
        tab = self.tabview.tab("Logs")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Activity Logs", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.log_text = scrolledtext.ScrolledText(
            tab,
            bg="#1e1e1e",
            fg="lightgreen",
            font=("Consolas", 9),
            insertbackground="white",
            wrap="word"
        )
        self.log_text.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        ctk.CTkButton(tab, text="Clear Logs", command=self.clear_logs, width=100).grid(
            row=2, column=0, padx=10, pady=10
        )

    def refresh_channel_list(self):
        for w in self.channel_listbox.winfo_children():
            w.destroy()
        for i, ch in enumerate(self.channels):
            btn = ctk.CTkButton(
                self.channel_listbox,
                text=f"Channel {i+1}: {ch['id']}",
                anchor="w",
                command=lambda idx=i: self.select_channel(idx)
            )
            btn.pack(pady=2, fill="x")

    def select_channel(self, index):
        if 0 <= index < len(self.channels):
            self.current_channel_index = index
            ch = self.channels[index]
            self.ch_id_entry.delete(0, "end")
            self.ch_id_entry.insert(0, ch['id'])
            self.ch_msg_text.delete("1.0", "end")
            self.ch_msg_text.insert("1.0", ch['message'])
            self.ch_int_entry.delete(0, "end")
            self.ch_int_entry.insert(0, str(ch['interval']))

    def add_channel(self):
        new_ch = {"id": "", "message": "", "interval": 7200}
        self.channels.append(new_ch)
        self.refresh_channel_list()
        self.current_channel_index = len(self.channels) - 1
        self.select_channel(self.current_channel_index)
        self.log("➕ Added channel")

    def remove_channel(self):
        if not self.channels:
            return
        idx = self.current_channel_index
        if idx is not None and 0 <= idx < len(self.channels):
            del self.channels[idx]
            self.current_channel_index = None
            self.refresh_channel_list()
            self.log("🗑️ Removed channel")

    def save_channel(self):
        if self.current_channel_index is None:
            self.log("Select a channel to save")
            return
        ch = self.channels[self.current_channel_index]
        ch['id'] = self.ch_id_entry.get().strip()
        ch['message'] = self.ch_msg_text.get("1.0", "end-1c").strip()
        try:
            ch['interval'] = max(60, int(self.ch_int_entry.get()))
        except:
            ch['interval'] = 7200
        self.log("💾 Channel saved")
        self.save_config()

    def save_config(self):
        token = self.token_entry.get().strip()
        webhook = self.webhook_entry.get().strip()

        if not token or not webhook:
            self.log("❌ Token and webhook required")
            return

        self.token = token
        self.webhook_url = webhook

        if self.collection is not None:
            try:
                self.collection.update_one(
                    {"_id": CONFIG_ID},
                    {"$set": {
                        "token": token,
                        "webhook_url": webhook,
                        "channels": self.channels
                    }},
                    upsert=True
                )
                self.log("💾 Config saved")
            except Exception as e:
                self.log(f"🔴 Save failed: {e}")

    def load_config(self):
        if self.collection is not None:
            try:
                doc = self.collection.find_one({"_id": CONFIG_ID})
                if doc:
                    self.token = doc.get("token", "")
                    self.webhook_url = doc.get("webhook_url", "")
                    self.channels = doc.get("channels", [])

                    if self.token and hasattr(self, 'token_entry'):
                        self.token_entry.insert(0, self.token)
                    if self.webhook_url and hasattr(self, 'webhook_entry'):
                        self.webhook_entry.insert(0, self.webhook_url)

                    self.refresh_channel_list()
                    if self.channels:
                        self.select_channel(0)
                    self.log("📥 Config loaded")
            except Exception as e:
                self.log(f"🔴 Load failed: {e}")

    def update_uptime(self):
        if self.is_running and self.uptime_label:
            self.uptime_label.configure(text=f"Uptime: {self.calculate_uptime()}")
        self.after(1000, self.update_uptime)

    def calculate_uptime(self):
        elapsed = datetime.now() - self.start_time
        h, rem = divmod(int(elapsed.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"

    def test_send(self):
        if not self.token or not self.webhook_url:
            self.log("❌ Save token/webhook first")
            return
        if not self.channels:
            self.log("❌ Add at least one channel")
            return
        ch = self.channels[0]
        self.log("📤 Testing post...")
        self.send_to_discord(ch['id'], ch['message'], is_test=True)

    def send_to_discord(self, channel_id, msg, is_test=False):
        current_time = datetime.now().strftime("%H:%M:%S%p")
        uptime = self.calculate_uptime()

        headers = {'Authorization': f'Bot {self.token}'}
        payload = {'content': msg}

        try:
            r = requests.post(f'https://discord.com/api/v9/channels/{channel_id}/messages', json=payload, headers=headers)
            r.raise_for_status()

            status_embed = {
                "title": "==[<a:boost:1134720034070077470> AUTO POST LOG <a:boost:1134720034070077470>]==",
                "color": 3447003,
                "description": f"**<a:discord:1139894640569491557> :** <#{channel_id}>\n"
                               f"**<a:verifyblack:1199426141879025716> :** **SENT SUCCESSFULLY**\n"
                               f"**<:Time:1264800539825143848> :** **{current_time}**\n"
                               f"**<a:EPTime:1243337079082061846> :** **{uptime}**\n"
                               f"{msg}",
                "footer": {"text": "Auto Posted By Tomoka"}
            }
            requests.post(self.webhook_url, json={"embeds": [status_embed]}, headers=headers)
            self.log("✅ Sent")

        except Exception as e:
            self.log(f"❌ Failed: {e}")
            status_embed = {
                "title": "<:meagaphone:1189539315806646353> Failed to Send Message <:meagaphone:1189539315806646353>",
                "color": 15158332,
                "description": f"**Discord Channel:** <#{channel_id}>\n**Time Sent:** {current_time}",
                "footer": {"text": "Auto Posted By Tomoka"}
            }
            try:
                requests.post(self.webhook_url, json={"embeds": [status_embed]}, headers=headers)
            except:
                pass

    def run_scheduler(self):
        while self.is_running:
            for ch in self.channels:
                if not self.is_running:
                    break
                self.send_to_discord(ch['id'], ch['message'])
                time.sleep(ch['interval'])

    def toggle_running(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not self.token or not self.webhook_url or not self.channels:
            self.log("❌ Fill all data first")
            return

        self.is_running = True
        self.start_btn.configure(text="Stop", fg_color="red")
        self.status_label.configure(text="Status: Running", text_color="green")
        self.log("▶️ Auto-posting started")

        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def stop(self):
        self.is_running = False
        self.start_btn.configure(text="Start", fg_color="green")
        self.status_label.configure(text="Status: Stopped", text_color="red")
        self.log("⏹️ Stopped")

    def clear_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self.log("🗑️ Logs cleared")

    def on_closing(self):
        if self.is_running:
            self.stop()
        self.save_config()
        self.destroy()


# === Run App ===
if __name__ == "__main__":
    app = DiscordAutoPoster()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()