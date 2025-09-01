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
        self.is_running = False
        self.bot_thread = None
        self.loop = None

        # Data
        self.token = ""
        self.webhook_url = ""
        self.channels = []

        # Reference for inner class
        DiscordAutoPoster.this_instance = self

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

        # === ALWAYS-VISIBLE: START / STOP ONLY ===
        control_frame = ctk.CTkFrame(self, height=50)
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

        ctk.CTkButton(tab, text="Save Settings", command=self.save_config).grid(
            row=2, column=0, columnspan=2, padx=10, pady=10
        )

    def setup_channels_tab(self):
        tab = self.tabview.tab("Channels")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkButton(tab, text="Add Channel", command=self.open_add_modal).grid(
            row=0, column=0, padx=10, pady=10
        )

        ctk.CTkLabel(tab, text="Channel List", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(tab, height=200)
        self.list_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        ctk.CTkButton(tab, text="Remove Selected", command=self.remove_selected, fg_color="red").grid(
            row=3, column=0, padx=10, pady=10
        )

        self.refresh_channel_list()

    def open_add_modal(self, edit_index=None):
        modal = ctk.CTkToplevel(self)
        modal.title("Add Channel" if edit_index is None else "Edit Channel")
        modal.geometry("400x350")
        modal.transient(self)
        modal.grab_set()

        modal.grid_columnconfigure(1, weight=1)

        idx = 0
        ctk.CTkLabel(modal, text="Channel ID", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        ch_id = ctk.CTkEntry(modal)
        ch_id.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="User ID (Ping)", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        user_id = ctk.CTkEntry(modal)
        user_id.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="Message", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="nw")
        message = ctk.CTkTextbox(modal, height=60)
        message.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="Interval (sec)", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        interval = ctk.CTkEntry(modal)
        interval.insert(0, "3600")
        interval.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="Attachments (one per line)", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="nw")
        attachments = ctk.CTkTextbox(modal, height=40)
        attachments.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        if edit_index is not None:
            ch = self.channels[edit_index]
            ch_id.insert(0, ch['id'])
            user_id.insert(0, ch.get('user_id', ''))
            message.insert("1.0", ch['message'])
            interval.delete(0, "end")
            interval.insert(0, str(ch['interval']))
            attachments.insert("1.0", "\n".join(ch.get('attachments', [])))

        def save():
            cid = ch_id.get().strip()
            uid = user_id.get().strip()
            msg = message.get("1.0", "end-1c").strip()
            attach = [f.strip() for f in attachments.get("1.0", "end-1c").strip().split("\n") if f.strip()]
            try:
                inter = max(60, int(interval.get()))
            except:
                inter = 3600

            if not cid or not msg:
                self.log("❌ Channel ID and message required")
                return

            if edit_index is None:
                self.channels.append({
                    "id": cid, "user_id": uid, "message": msg,
                    "interval": inter, "attachments": attach,
                    "selected": False
                })
                self.log("✅ Channel added")
            else:
                self.channels[edit_index].update({
                    "id": cid, "user_id": uid, "message": msg,
                    "interval": inter, "attachments": attach
                })
                self.log("✅ Channel updated")

            self.refresh_channel_list()
            self.save_config()
            modal.destroy()

        ctk.CTkButton(modal, text="Save", command=save).grid(row=idx, column=0, columnspan=2, pady=10)

    def refresh_channel_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        for i, ch in enumerate(self.channels):
            ch.setdefault("selected", False)
            item_frame = ctk.CTkFrame(self.list_frame)
            item_frame.pack(fill="x", pady=2)

            var = ctk.BooleanVar(value=ch["selected"])
            ch["selected_var"] = var

            def make_toggle(idx):
                return lambda: self.toggle_select(idx)

            chk = ctk.CTkCheckBox(item_frame, text="", width=20, variable=var, command=make_toggle(i))
            chk.pack(side="left", padx=5)

            label = ctk.CTkLabel(item_frame, text=f"Channel: {ch['id']}", cursor="hand2")
            label.pack(side="left", padx=5)
            label.bind("<Button-1>", lambda e, idx=i: self.open_add_modal(edit_index=idx))

    def toggle_select(self, index):
        self.channels[index]["selected"] = not self.channels[index]["selected"]

    def remove_selected(self):
        before = len(self.channels)
        self.channels = [ch for ch in self.channels if not ch.get("selected", False)]
        removed = before - len(self.channels)
        if removed:
            self.log(f"🗑️ Removed {removed} channel(s)")
            self.refresh_channel_list()
            self.save_config()
        else:
            self.log("❌ No channels selected")

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

        if not token or not webhook:
            self.log("❌ Token & webhook required")
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
            except Exception as e:
                self.log(f"🔴 Save failed: {e}")

    def load_config(self):
        if self.collection is not None:
            try:
                doc = self.collection.find_one({"_id": CONFIG_ID})
                if doc:
                    self.token = doc.get("token", "")
                    self.webhook_url = doc.get("webhook_url", "")
                    raw_channels = doc.get("channels", [])
                    self.channels = []
                    for ch in raw_channels:
                        ch.setdefault("selected", False)
                        self.channels.append(ch)

                    if self.token and hasattr(self, 'token_entry'):
                        self.token_entry.insert(0, self.token)
                    if self.webhook_url and hasattr(self, 'webhook_entry'):
                        self.webhook_entry.insert(0, self.webhook_url)

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

        # ✅ Always update instance reference before start
        DiscordAutoPoster.this_instance = self

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
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        client = commands.Bot(command_prefix='!', intents=discord.Intents.all(), self_bot=True)

        class AutoPosterLogic:
            def __init__(self):
                # ✅ Use instance data via this_instance
                self.token = DiscordAutoPoster.this_instance.token
                self.channels = DiscordAutoPoster.this_instance.channels
                self.webhook_url = DiscordAutoPoster.this_instance.webhook_url
                self.start_time = time.time()
                self.total_posts = 0

            async def send_to_webhook(self, user_id: int, channel_id: int, status: str, message_content: str):
                if not self.webhook_url:
                    return
                try:
                    user = client.get_user(user_id) or await client.fetch_user(user_id)
                    channel = client.get_channel(channel_id)
                    current_time = datetime.datetime.now(datetime.timezone.utc)
                    uptime = self.format_uptime(time.time() - self.start_time)
                    next_post = self.format_time_remaining(60)  # dummy

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
                                DiscordAutoPoster.this_instance.log("✓ Webhook sent")
                except Exception as e:
                    DiscordAutoPoster.this_instance.log(f"Webhook error: {e}")

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
                        DiscordAutoPoster.this_instance.log(f"Channel {channel_id} not found")
                        return False
                    files = [discord.File(f) for f in attachments if os.path.exists(f)]
                    await channel.send(content=message, files=files)
                    self.total_posts += 1
                    DiscordAutoPoster.this_instance.log(f"✅ Posted to {channel.name}")
                    return True
                except Exception as e:
                    DiscordAutoPoster.this_instance.log(f"❌ Error: {e}")
                    return False

            async def run_loop(self):
                DiscordAutoPoster.this_instance.log("Auto-post loop started")
                while DiscordAutoPoster.this_instance.is_running:
                    for ch in self.channels:
                        success = await self.send_message(int(ch["id"]), ch["message"], ch.get("attachments", []))
                        status = "✅ Active" if success else "❌ Error"
                        if self.webhook_url:
                            await self.send_to_webhook(client.user.id, int(ch["id"]), status, ch["message"])
                        await asyncio.sleep(ch["interval"])

        poster = AutoPosterLogic()

        @client.event
        async def on_ready():
            DiscordAutoPoster.this_instance.log(f"🟢 Logged in as {client.user}")
            await poster.run_loop()

        try:
            self.loop.run_until_complete(client.start(self.token, bot=False))
        except Exception as e:
            DiscordAutoPoster.this_instance.log(f"🔴 Login failed: {e}")

    def on_closing(self):
        if self.is_running:
            self.stop()
        self.save_config()
        self.destroy()


if __name__ == "__main__":
    app = DiscordAutoPoster()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()