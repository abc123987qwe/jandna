import customtkinter as ctk
from tkinter import scrolledtext, messagebox
import threading
import time
import schedule
import requests
from datetime import datetime
from pymongo import MongoClient
import sys

# =============== 🔐 YOUR MONGODB URI ===============
MONGO_URI = "mongodb+srv://midknight:midkpost9987@cluster1.wp9evkm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"
DB_NAME = "discord_bot"
COLLECTION_NAME = "auto_poster_config"
CONFIG_ID = "main_config"  # Will be updated to user/bot ID later
# ===================================================

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DiscordAutoPoster(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Poster")
        self.geometry("680x480")
        self.minsize(600, 400)

        # Runtime
        self.start_time = datetime.now()
        self.is_running = False
        self.scheduler_thread = None

        # Data
        self.token = ""
        self.webhook_url = ""
        self.channels = {}
        self.uptime_label = None

        # Connect to MongoDB
        self.collection = None
        self.connect_mongo()

        # Setup UI
        self.setup_ui()

        # Load config
        self.load_config()

    def connect_mongo(self):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[DB_NAME]
            self.collection = db[COLLECTION_NAME]
            self.log("🟢 Connected to MongoDB")
        except Exception as e:
            self.log(f"🔴 DB Error: {e}")
            self.collection = None

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(self, text="Discord Auto Poster", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        # Main Frame
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure((0,1,2,3,4,5), weight=1)

        # Token
        ctk.CTkLabel(main_frame, text="Bot Token", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.token_entry = ctk.CTkEntry(main_frame, placeholder_text="Paste token here", show="•")
        self.token_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")

        # Webhook
        ctk.CTkLabel(main_frame, text="Webhook URL", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.webhook_entry = ctk.CTkEntry(main_frame, placeholder_text="https://discord.com/api/webhooks/...")
        self.webhook_entry.grid(row=1, column=1, padx=(0,10), pady=5, sticky="ew")

        # Channel ID
        ctk.CTkLabel(main_frame, text="Channel ID", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.channel_entry = ctk.CTkEntry(main_frame, placeholder_text="1234567890")
        self.channel_entry.grid(row=2, column=1, padx=(0,10), pady=5, sticky="ew")

        # Message
        ctk.CTkLabel(main_frame, text="Message", font=ctk.CTkFont(size=12)).grid(row=3, column=0, padx=10, pady=5, sticky="nw")
        self.message_text = ctk.CTkTextbox(main_frame, height=80)
        self.message_text.grid(row=3, column=1, padx=(0,10), pady=5, sticky="ew")

        # Interval
        ctk.CTkLabel(main_frame, text="Interval (sec)", font=ctk.CTkFont(size=12)).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.interval_entry = ctk.CTkEntry(main_frame)
        self.interval_entry.insert(0, "7200")
        self.interval_entry.grid(row=4, column=1, padx=(0,10), pady=5, sticky="ew")

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky="ew")
        btn_frame.grid_columnconfigure((0,1,2), weight=1)

        self.save_btn = ctk.CTkButton(btn_frame, text="Save", command=self.save_config, width=80)
        self.save_btn.grid(row=0, column=0, padx=5)

        self.start_btn = ctk.CTkButton(btn_frame, text="Start", command=self.toggle_running, width=80, fg_color="green")
        self.start_btn.grid(row=0, column=1, padx=5)

        self.test_btn = ctk.CTkButton(btn_frame, text="Test", command=self.test_send, width=80)
        self.test_btn.grid(row=0, column=2, padx=5)

        # Logs
        ctk.CTkLabel(self, text="Logs", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=10, pady=(0,5), sticky="w")
        self.log_text = scrolledtext.ScrolledText(
            self, bg="#2b2b2b", fg="lightgray", font=("Consolas", 9), height=8
        )
        self.log_text.grid(row=3, column=0, padx=10, pady=(0,5), sticky="nsew")

        # Status bar
        status_frame = ctk.CTkFrame(self, height=20)
        status_frame.grid(row=4, column=0, padx=10, pady=(0,10), sticky="ew")
        status_frame.grid_propagate(False)
        status_frame.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(status_frame, text="Stopped", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=0, padx=10)

        self.uptime_label = ctk.CTkLabel(status_frame, text="Uptime: 0h 0m 0s", font=ctk.CTkFont(size=12))
        self.uptime_label.grid(row=0, column=1, padx=10)

    def calculate_uptime(self):
        elapsed = datetime.now() - self.start_time
        h, rem = divmod(int(elapsed.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"

    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}\n"
        self.log_text.config(state="normal")
        self.log_text.insert("end", entry)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def save_config(self):
        token = self.token_entry.get().strip()
        webhook = self.webhook_entry.get().strip()
        channel_id = self.channel_entry.get().strip()
        message = self.message_text.get("1.0", "end-1c").strip()
        interval_str = self.interval_entry.get().strip()

        if not all([token, webhook, channel_id, message, interval_str]):
            self.log("❌ All fields are required!")
            return

        try:
            interval = int(interval_str)
            if interval < 60:
                raise ValueError
        except:
            self.log("❌ Interval must be number >= 60")
            return

        # Save to object
        self.token = token
        self.webhook_url = webhook
        self.channels = { "default": message }
        self.current_channel_id = channel_id
        self.current_interval = interval

        # Save to MongoDB
        if self.collection:
            try:
                self.collection.update_one(
                    {"_id": CONFIG_ID},
                    {"$set": {
                        "token": token,
                        "webhook_url": webhook,
                        "channel_id": channel_id,
                        "message": message,
                        "interval": interval
                    }},
                    upsert=True
                )
                self.log("💾 Config saved")
            except Exception as e:
                self.log(f"🔴 Save failed: {e}")
        else:
            self.log("🔴 Not saving: DB disconnected")

    def load_config(self):
        if not self.collection:
            return
        try:
            doc = self.collection.find_one({"_id": CONFIG_ID})
            if doc:
                defaults = {
                    "token": "",
                    "webhook_url": "",
                    "channel_id": "",
                    "message": "",
                    "interval": 7200
                }
                for k, v in defaults.items():
                    setattr(self, k, doc.get(k, v))

                # Fill UI
                self.token_entry.insert(0, self.token)
                self.webhook_entry.insert(0, self.webhook_url)
                self.channel_entry.insert(0, self.channel_id)
                self.message_text.insert("1.0", self.message)
                self.interval_entry.delete(0, "end")
                self.interval_entry.insert(0, str(self.interval))

                self.log("📥 Config loaded")
        except Exception as e:
            self.log(f"🔴 Load failed: {e}")

    def test_send(self):
        self.log("📤 Sending test message...")
        self.send_to_discord(self.channel_id, self.message, is_test=True)

    def send_to_discord(self, channel_id, msg, is_test=False):
        current_time = datetime.now().strftime("%H:%M:%S%p")
        uptime = self.calculate_uptime()

        headers = {'Authorization': self.token}
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
            self.log("✅ Sent & logged")

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
            schedule.run_pending()
            time.sleep(1)

    def toggle_running(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not all([self.token, self.webhook_url, self.current_channel_id]):
            self.log("❌ Fill and save config first!")
            return

        interval = getattr(self, 'current_interval', 7200)
        schedule.clear()
        schedule.every(interval).seconds.do(self.send_to_discord, self.current_channel_id, self.message)

        self.is_running = True
        self.start_btn.configure(text="Stop", fg_color="red")
        self.status_label.configure(text="Running", text_color="green")
        self.log(f"▶️ Started (every {interval}s)")

        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def stop(self):
        self.is_running = False
        schedule.clear()
        self.start_btn.configure(text="Start", fg_color="green")
        self.status_label.configure(text="Stopped", text_color="red")
        self.log("⏹️ Stopped")

    def update_uptime(self):
        if self.uptime_label:
            self.uptime_label.configure(text=f"Uptime: {self.calculate_uptime()}")
        if self.is_running:
            self.after(1000, self.update_uptime)

    def on_closing(self):
        if self.is_running:
            self.stop()
        self.save_config()
        self.destroy()

# --- Run App ---
if __name__ == "__main__":
    app = DiscordAutoPoster()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.update_uptime()
    app.mainloop()