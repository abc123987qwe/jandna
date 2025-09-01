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

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DiscordAutoPoster(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 🔽 TINY WINDOW — like CMD
        self.title("Auto Poster")
        self.geometry("600x400")  # Small, terminal-like
        self.resizable(False, False)  # Fixed size

        # Runtime
        self.start_time = datetime.now()
        self.is_running = False

        # Data
        self.token = ""
        self.webhook_url = ""
        self.channel_id = ""
        self.message = ""
        self.interval = 7200

        # UI must be created FIRST
        self.setup_ui()  # ← Creates self.log_text

        # Now safe to connect and load
        self.collection = None
        self.connect_mongo()
        self.load_config()

        # Start uptime updates
        self.update_uptime()

    def connect_mongo(self):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            db = client[DB_NAME]
            self.collection = db[COLLECTION_NAME]
            self.log("🟢 DB Connected")
        except Exception as e:
            self.log(f"🔴 DB Error: {e}")

    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t}] {msg}\n"

        # ✅ Safe: only use log_text if it exists
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.config(state="normal")
            self.log_text.insert("end", entry)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        else:
            print(entry.strip())

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Minimal header
        ctk.CTkLabel(self, text="Auto Poster", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=10, pady=10
        )

        # Frame for inputs
        input_frame = ctk.CTkFrame(self, height=180)
        input_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        input_frame.grid_propagate(False)
        input_frame.grid_columnconfigure(1, weight=1)

        # Token
        ctk.CTkLabel(input_frame, text="Token", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.token_entry = ctk.CTkEntry(input_frame, placeholder_text="Bot token", height=24)
        self.token_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")

        # Webhook
        ctk.CTkLabel(input_frame, text="Webhook", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.webhook_entry = ctk.CTkEntry(input_frame, placeholder_text="https://discord.com/api/webhooks/...", height=24)
        self.webhook_entry.grid(row=1, column=1, padx=(0,10), pady=5, sticky="ew")

        # Channel ID
        ctk.CTkLabel(input_frame, text="Channel", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.channel_entry = ctk.CTkEntry(input_frame, placeholder_text="1234567890", height=24)
        self.channel_entry.grid(row=2, column=1, padx=(0,10), pady=5, sticky="ew")

        # Interval
        ctk.CTkLabel(input_frame, text="Interval", font=ctk.CTkFont(size=12)).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.interval_entry = ctk.CTkEntry(input_frame, placeholder_text="7200", height=24)
        self.interval_entry.insert(0, "7200")
        self.interval_entry.grid(row=3, column=1, padx=(0,10), pady=5, sticky="ew")

        # Message
        ctk.CTkLabel(self, text="Message", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=10, pady=(0,5), sticky="w")
        self.message_text = ctk.CTkTextbox(self, height=60)
        self.message_text.grid(row=3, column=0, padx=10, pady=(0,5), sticky="ew")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, pady=5)

        self.save_btn = ctk.CTkButton(btn_frame, text="Save", command=self.save_config, width=80, height=25)
        self.save_btn.grid(row=0, column=0, padx=5)

        self.start_btn = ctk.CTkButton(btn_frame, text="Start", command=self.toggle_running, width=80, height=25, fg_color="green")
        self.start_btn.grid(row=0, column=1, padx=5)

        self.test_btn = ctk.CTkButton(btn_frame, text="Test", command=self.test_send, width=80, height=25)
        self.test_btn.grid(row=0, column=2, padx=5)

        # Logs
        ctk.CTkLabel(self, text="Logs", font=ctk.CTkFont(size=12)).grid(row=5, column=0, padx=10, pady=(0,5), sticky="w")
        self.log_text = scrolledtext.ScrolledText(
            self,
            bg="#2b2b2b",
            fg="lightgray",
            font=("Consolas", 9),
            height=6,
            wrap="word"
        )
        self.log_text.grid(row=6, column=0, padx=10, pady=(0,5), sticky="ew")

        # Status bar (Uptime)
        self.status_label = ctk.CTkLabel(self, text="Status: Stopped", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=7, column=0, padx=10, pady=(0,5), sticky="w")

        self.uptime_label = ctk.CTkLabel(self, text="Uptime: 0h 0m 0s", font=ctk.CTkFont(size=12))
        self.uptime_label.grid(row=8, column=0, padx=10, pady=(0,10), sticky="w")

    def calculate_uptime(self):
        elapsed = datetime.now() - self.start_time
        h, rem = divmod(int(elapsed.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"

    def update_uptime(self):
        if self.is_running and self.uptime_label:
            self.uptime_label.configure(text=f"Uptime: {self.calculate_uptime()}")
        self.after(1000, self.update_uptime)

    def save_config(self):
        token = self.token_entry.get().strip()
        webhook = self.webhook_entry.get().strip()
        channel_id = self.channel_entry.get().strip()
        message = self.message_text.get("1.0", "end-1c").strip()
        interval_str = self.interval_entry.get().strip()

        if not all([token, webhook, channel_id, message, interval_str]):
            self.log("❌ All fields required")
            return

        try:
            interval = max(60, int(interval_str))
        except:
            self.log("❌ Invalid interval")
            return

        # Save to memory
        self.token = token
        self.webhook_url = webhook
        self.channel_id = channel_id
        self.message = message
        self.interval = interval

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
                self.log("💾 Saved to cloud")
            except Exception as e:
                self.log(f"🔴 Save failed: {e}")

    def load_config(self):
        if not self.collection:
            return
        try:
            doc = self.collection.find_one({"_id": CONFIG_ID})
            if doc:
                self.token = doc.get("token", "")
                self.webhook_url = doc.get("webhook_url", "")
                self.channel_id = doc.get("channel_id", "")
                self.message = doc.get("message", "")
                self.interval = doc.get("interval", 7200)

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
        self.log("📤 Testing...")
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
            schedule.run_pending()
            time.sleep(1)

    def toggle_running(self):
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        if not all([self.token, self.webhook_url, self.channel_id]):
            self.log("❌ Fill & save first")
            return

        schedule.clear()
        schedule.every(self.interval).seconds.do(self.send_to_discord, self.channel_id, self.message)

        self.is_running = True
        self.start_btn.configure(text="Stop", fg_color="red")
        self.status_label.configure(text="Status: Running", text_color="green")
        self.log(f"▶️ Started ({self.interval}s)")

        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def stop(self):
        self.is_running = False
        schedule.clear()
        self.start_btn.configure(text="Start", fg_color="green")
        self.status_label.configure(text="Status: Stopped", text_color="red")
        self.log("⏹️ Stopped")

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