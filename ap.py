import customtkinter as ctk
from tkinter import scrolledtext
import threading
import asyncio
import discord
from discord.ext import commands
import aiohttp
import time
import datetime
from pymongo import MongoClient
import os
import sys

# =============== 🔐 YOUR MONGODB URI ===============
MONGO_URI = "mongodb+srv://midknight:midkpost9987@cluster1.wp9evkm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"
DB_NAME = "discord_bot"
COLLECTION_NAME = "auto_poster_config"
CONFIG_ID = "main_config"
# ===================================================

# GUI Settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DiscordAutoPoster(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Poster")
        self.geometry("600x500")
        self.resizable(False, False)

        # Runtime
        self.is_running = False
        self.bot_task = None
        self.loop = None

        # Data
        self.token = ""
        self.webhook_url = ""
        self.channels = []
        self.delay_minutes = 1

        # Connect to MongoDB
        self.collection = None
        self.connect_mongo()

        # Setup UI
        self.setup_ui()

        # Load config after UI
        self.load_config()

    def connect_mongo(self):
        try:
            client_db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            client_db.admin.command("ping")
            db = client_db[DB_NAME]
            self.collection = db[COLLECTION_NAME]
            self.log("🟢 DB: Connected")
        except Exception as e:
            self.log(f"🔴 DB: {e}")

    def log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
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
        self.grid_rowconfigure(1, weight=1)

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

        # === ALWAYS-VISIBLE: START / STOP ===
        control_frame = ctk.CTkFrame(self, height=60)
        control_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        control_frame.grid_propagate(False)
        control_frame.grid_columnconfigure(1, weight=1)

        self.status_label = ctk.CTkLabel(control_frame, text="Status: Stopped", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=0, padx=10, sticky="w")

        self.start_btn = ctk.CTkButton(
            control_frame, text="Start", command=self.toggle_running,
            width=80, height=28, fg_color="green"
        )
        self.start_btn.grid(row=0, column=1, padx=10)

    def setup_token_tab(self):
        tab = self.tabview.tab("Token")
        tab.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="User Token", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.token_entry = ctk.CTkEntry(tab, placeholder_text="Paste your user token", show="•")
        self.token_entry.grid(row=0, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkLabel(tab, text="Webhook URL", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.webhook_entry = ctk.CTkEntry(tab, placeholder_text="https://discord.com/api/webhooks/...")
        self.webhook_entry.grid(row=1, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkLabel(tab, text="Delay (min)", font=ctk.CTkFont(size=12)).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.delay_entry = ctk.CTkEntry(tab)
        self.delay_entry.insert(0, "1")
        self.delay_entry.grid(row=2, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkButton(tab, text="Save Settings", command=self.save_config).grid(
            row=3, column=0, columnspan=2, padx=10, pady=10
        )

    def setup_channels_tab(self):
        tab = self.tabview.tab("Channels")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(tab, text="Channel List", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.channel_listbox = ctk.CTkScrollableFrame(tab, height=160)
        self.channel_listbox.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=5)
        ctk.CTkButton(btn_frame, text="Add", command=self.add_channel, width=80).grid(row=0, column=0, padx=5)
        ctk.CTkButton(btn_frame, text="Remove", command=self.remove_channel, width=80, fg_color="red").grid(row=0, column=1, padx=5)

        self.refresh_channel_list()

    def refresh_channel_list(self):
        for w in self.channel_listbox.winfo_children():
            w.destroy()
        for i, ch in enumerate(self.channels):
            name = ch.get("id", "Unknown")
            btn = ctk.CTkButton(
                self.channel_listbox,
                text=f"Ch {i+1}: {name}",
                anchor="w",
                command=lambda idx=i: self.edit_channel(idx)
            )
            btn.pack(pady=2, fill="x")

    def add_channel(self):
        self.edit_channel(None)

    def edit_channel(self, index):
        modal = ctk.CTkToplevel(self)
        modal.title("Add Channel" if index is None else "Edit Channel")
        modal.geometry("400x300")
        modal.transient(self)
        modal.grab_set()

        modal.grid_columnconfigure(1, weight=1)

        idx = 0
        ctk.CTkLabel(modal, text="Channel ID", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        ch_id = ctk.CTkEntry(modal)
        ch_id.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="Message", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        message = ctk.CTkTextbox(modal, height=60)
        message.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="Attachments", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        attachments = ctk.CTkTextbox(modal, height=60)
        attachments.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        if index is not None:
            ch = self.channels[index]
            ch_id.insert(0, ch['id'])
            message.insert("1.0", ch['message'])
            attachments.insert("1.0", "\n".join(ch.get('attachments', [])))

        def save():
            cid = ch_id.get().strip()
            msg = message.get("1.0", "end-1c").strip()
            attach = [f.strip() for f in attachments.get("1.0", "end-1c").strip().split("\n") if f.strip()]
            if not cid or not msg:
                self.log("❌ ID and message required")
                return
            if index is None:
                self.channels.append({"id": cid, "message": msg, "attachments": attach})
                self.log("✅ Channel added")
            else:
                self.channels[index] = {"id": cid, "message": msg, "attachments": attach}
                self.log("✅ Channel updated")
            self.refresh_channel_list()
            self.save_config()
            modal.destroy()

        ctk.CTkButton(modal, text="Save", command=save).grid(row=idx, column=0, columnspan=2, pady=10)

    def remove_channel(self):
        if not self.channels:
            return
        self.channels.pop()
        self.refresh_channel_list()
        self.save_config()
        self.log("🗑️ Channel removed")

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

    def save_config(self):
        token = self.token_entry.get().strip()
        webhook = self.webhook_entry.get().strip()
        delay_str = self.delay_entry.get().strip()

        if not token or not webhook or not delay_str:
            self.log("❌ All fields required")
            return

        try:
            delay = max(1, int(delay_str))
        except:
            delay = 1

        self.token = token
        self.webhook_url = webhook
        self.delay_minutes = delay

        if self.collection is not None:
            try:
                self.collection.update_one(
                    {"_id": CONFIG_ID},
                    {"$set": {
                        "token": token,
                        "webhook_url": webhook,
                        "delay_in_minutes": delay,
                        "channels": self.channels
                    }},
                    upsert=True
                )
                self.log("💾 Config saved to cloud")
            except Exception as e:
                self.log(f"🔴 Save failed: {e}")

    def load_config(self):
        if self.collection is not None:
            try:
                doc = self.collection.find_one({"_id": CONFIG_ID})
                if doc:
                    self.token = doc.get("token", "")
                    self.webhook_url = doc.get("webhook_url", "")
                    self.delay_minutes = doc.get("delay_in_minutes", 1)
                    self.channels = doc.get("channels", [])

                    if self.token and hasattr(self, 'token_entry'):
                        self.token_entry.insert(0, self.token)
                    if self.webhook_url and hasattr(self, 'webhook_entry'):
                        self.webhook_entry.insert(0, self.webhook_url)
                    self.delay_entry.delete(0, "end")
                    self.delay_entry.insert(0, str(self.delay_minutes))

                    self.refresh_channel_list()
                    self.log("📥 Config loaded")
            except Exception as e:
                self.log(f"🔴 Load failed: {e}")

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
        self.log("▶️ Starting bot...")

        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def stop(self):
        self.is_running = False
        self.start_btn.configure(text="Start", fg_color="green")
        self.status_label.configure(text="Status: Stopped", text_color="red")
        self.log("⏹️ Bot stopped")

    def run_bot(self):
        # Run asyncio loop in thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        client = commands.Bot(
            command_prefix='!',
            intents=discord.Intents.all(),
            self_bot=True
        )

        class AutoPosterLogic:
            def __init__(self):
                self.token = DiscordAutoPoster.token
                self.channels = DiscordAutoPoster.channels
                self.delay = DiscordAutoPoster.delay_minutes * 60
                self.webhook_url = DiscordAutoPoster.webhook_url
                self.start_time = time.time()
                self.total_posts = 0
                self.next_post_time = time.time() + self.delay

            async def send_to_webhook(self, user_id: int, channel_id: int, status: str, message_content: str):
                if not self.webhook_url:
                    return
                try:
                    user = client.get_user(user_id) or await client.fetch_user(user_id)
                    channel = client.get_channel(channel_id)
                    current_time = datetime.datetime.now(datetime.timezone.utc)
                    uptime = self.format_uptime(time.time() - self.start_time)
                    next_post = self.format_time_remaining(self.next_post_time - time.time())

                    webhook_data = {
                        "embeds": [{
                            "title": "<a:siren:721442260184727653> Auto Post Notification <a:siren:721442260184727653>",
                            "description": (
                                f"**<a:logistique2:905561418575798293> Channel:** {f'#{channel.name}' if channel else f'<#{channel_id}>'}\n"
                                f"**<:bot:1283989664813809747> Account:** {user.name if user else 'Unknown'}\n"
                                f"**<a:greenping:1247486899531288637> Status:** {status}\n"
                                f"**<a:hsevents_a:1278005070990151752> Total Posts:** {self.total_posts}\n"
                                f"**<a:EPTime:1243341200195321916> Next Post In:** {next_post}\n"
                                f"**<:uptime:1315839127362736239> Uptime:** {uptime}\n\n"
                                f"**Posted Message:**\n{message_content}\n\n"
                            ),
                            "color": 0x5865F2,
                            "footer": {"text": "Auto Post by Tomoka Community"},
                            "timestamp": current_time.isoformat(),
                            "thumbnail": {"url": str(user.avatar.url) if user and user.avatar.url else ""}
                        }]
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(self.webhook_url, json=webhook_data) as response:
                            if response.status == 204:
                                DiscordAutoPoster.log("✓ Webhook sent")
                except Exception as e:
                    DiscordAutoPoster.log(f"Webhook error: {e}")

            def format_uptime(self, seconds: float) -> str:
                h, r = divmod(int(seconds), 3600)
                m, s = divmod(r, 60)
                return f"{h}h {m}m {s}s"

            def format_time_remaining(self, seconds: float) -> str:
                if seconds <= 0: return "Now"
                m, s = divmod(int(seconds), 60)
                return f"{m}m {s}s"

            async def send_message(self, channel_id: int, message: str, attachments: list):
                try:
                    channel = client.get_channel(channel_id)
                    if not channel:
                        DiscordAutoPoster.log(f"Channel {channel_id} not found")
                        return False
                    files = [discord.File(f) for f in attachments if os.path.exists(f)]
                    await channel.send(content=message, files=files)
                    self.total_posts += 1
                    DiscordAutoPoster.log(f"Posted to {channel.name}")
                    return True
                except Exception as e:
                    DiscordAutoPoster.log(f"Error: {e}")
                    return False

            async def run_loop(self):
                DiscordAutoPoster.log("Auto-post loop started")
                while DiscordAutoPoster.is_running:
                    self.next_post_time = time.time() + self.delay
                    for ch in self.channels:
                        success = await self.send_message(int(ch["id"]), ch["message"], ch.get("attachments", []))
                        status = "✅ Active" if success else "❌ Error"
                        if self.webhook_url:
                            await self.send_to_webhook(client.user.id, int(ch["id"]), status, ch["message"])
                    while time.time() < self.next_post_time and DiscordAutoPoster.is_running:
                        remaining = self.next_post_time - time.time()
                        DiscordAutoPoster.log(f"Next post in {self.format_time_remaining(remaining)}")
                        await asyncio.sleep(1)

        poster = AutoPosterLogic()

        @client.event
        async def on_ready():
            DiscordAutoPoster.log(f"Logged in as {client.user}")
            await poster.run_loop()

        try:
            self.loop.run_until_complete(client.start(poster.token, bot=False))
        except Exception as e:
            DiscordAutoPoster.log(f"Login failed: {e}")

    def on_closing(self):
        if self.is_running:
            self.stop()
        self.save_config()
        self.destroy()


if __name__ == "__main__":
    app = DiscordAutoPoster()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()