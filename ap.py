import customtkinter as ctk
from tkinter import scrolledtext
import threading
import time
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
        self.channels = []  # {id, user_id, message, interval, selected}

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

        ctk.CTkLabel(tab, text="Bot Token", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.token_entry = ctk.CTkEntry(tab, placeholder_text="Paste bot token", show="•")
        self.token_entry.grid(row=0, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkLabel(tab, text="Webhook URL", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.webhook_entry = ctk.CTkEntry(tab, placeholder_text="https://discord.com/api/webhooks/...", show="•")
        self.webhook_entry.grid(row=1, column=1, padx=(0,10), pady=10, sticky="ew")

        ctk.CTkButton(tab, text="Save Settings", command=self.save_config).grid(
            row=2, column=0, columnspan=2, padx=10, pady=10
        )

    def setup_channels_tab(self):
        tab = self.tabview.tab("Channels")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Add Button
        ctk.CTkButton(tab, text="Add Channel", command=self.open_add_modal).grid(
            row=0, column=0, padx=10, pady=10
        )

        # List Label
        ctk.CTkLabel(tab, text="Channel List", font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=10, pady=5, sticky="w")

        # ✅ Box List with Checkboxes
        self.list_frame = ctk.CTkScrollableFrame(tab, height=200)
        self.list_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        # Remove Button
        ctk.CTkButton(tab, text="Remove Selected", command=self.remove_selected, fg_color="red").grid(
            row=3, column=0, padx=10, pady=10
        )

        self.refresh_channel_list()

    def open_add_modal(self, edit_index=None):
        # Shared modal for Add/Edit
        modal = ctk.CTkToplevel(self)
        modal.title("Add Channel" if edit_index is None else "Edit Channel")
        modal.geometry("400x300")
        modal.transient(self)
        modal.grab_set()
        modal.focus()

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

        ctk.CTkLabel(modal, text="Interval (sec)", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="w")
        interval = ctk.CTkEntry(modal)
        interval.insert(0, "7200")
        interval.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        ctk.CTkLabel(modal, text="Message", font=ctk.CTkFont(size=12)).grid(row=idx, column=0, padx=10, pady=10, sticky="nw")
        message = ctk.CTkTextbox(modal, height=60)
        message.grid(row=idx, column=1, padx=(0,10), pady=10, sticky="ew")
        idx += 1

        # Load data if editing
        if edit_index is not None:
            ch = self.channels[edit_index]
            ch_id.insert(0, ch['id'])
            user_id.insert(0, ch.get('user_id', ''))
            interval.delete(0, "end")
            interval.insert(0, str(ch['interval']))
            message.insert("1.0", ch['message'])

        def save():
            cid = ch_id.get().strip()
            uid = user_id.get().strip()
            msg = message.get("1.0", "end-1c").strip()
            try:
                inter = max(60, int(interval.get()))
            except:
                inter = 7200

            if not cid or not msg:
                self.log("❌ Channel ID and message required")
                return

            if edit_index is None:
                self.channels.append({
                    "id": cid,
                    "user_id": uid,
                    "message": msg,
                    "interval": inter,
                    "selected": False
                })
                self.log("✅ Channel added")
            else:
                self.channels[edit_index].update({
                    "id": cid,
                    "user_id": uid,
                    "message": msg,
                    "interval": inter
                })
                self.log("✅ Channel updated")

            self.refresh_channel_list()
            self.save_config()
            modal.destroy()

        ctk.CTkButton(modal, text="Save", command=save).grid(row=idx, column=0, columnspan=2, pady=20)

    def refresh_channel_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        for i, ch in enumerate(self.channels):
            item_frame = ctk.CTkFrame(self.list_frame)
            item_frame.pack(fill="x", pady=2)

            # Checkbox
            var = ctk.BooleanVar(value=ch.get("selected", False))
            ch['selected_var'] = var  # Store var reference

            def make_toggle(idx):
                return lambda: self.toggle_select(idx)

            chk = ctk.CTkCheckBox(item_frame, text="", width=20, variable=var, command=make_toggle(i))
            chk.pack(side="left", padx=5)

            # Label
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
                    self.channels = doc.get("channels", [])

                    if self.token and hasattr(self, 'token_entry'):
                        self.token_entry.insert(0, self.token)
                    if self.webhook_url and hasattr(self, 'webhook_entry'):
                        self.webhook_entry.insert(0, self.webhook_url)

                    self.refresh_channel_list()
                    self.log("📥 Config loaded")
            except Exception as e:
                self.log(f"🔴 Load failed: {e}")

    def update_uptime(self):
        if self.is_running and self.status_label:
            uptime = self.calculate_uptime()
            self.status_label.configure(text=f"Status: Running | {uptime}")
        elif not self.is_running:
            self.status_label.configure(text="Status: Stopped")
        self.after(1000, self.update_uptime)

    def calculate_uptime(self):
        elapsed = datetime.now() - self.start_time
        h, rem = divmod(int(elapsed.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        return f"Uptime: {h}h {m}m {s}s"

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
        self.log("▶️ Auto-posting started")
        self.update_uptime()

        self.posting_thread = threading.Thread(target=self.run_posting, daemon=True)
        self.posting_thread.start()

    def stop(self):
        self.is_running = False
        self.start_btn.configure(text="Start", fg_color="green")
        self.log("⏹️ Stopped")

    def run_posting(self):
        while self.is_running:
            for ch in self.channels:
                if not self.is_running:
                    break
                self.send_to_discord(ch['id'], ch['message'])
                time.sleep(ch['interval'])

    def send_to_discord(self, channel_id, msg):
        if not self.token or not channel_id or not msg:
            return

        headers = {'Authorization': f'Bot {self.token.strip()}'}
        payload = {'content': msg}

        try:
            r = requests.post(f'https://discord.com/api/v9/channels/{channel_id}/messages', json=payload, headers=headers)
            r.raise_for_status()
            self.log(f"✅ Sent to {channel_id}")
        except requests.exceptions.HTTPError as e:
            if r.status_code == 401:
                self.log("🔴 401: Invalid token! Use a valid Bot Token")
            else:
                self.log(f"🔴 HTTP {r.status_code}: {r.text}")
        except Exception as e:
            self.log(f"🔴 Network error: {e}")

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