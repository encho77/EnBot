import discord
from discord import app_commands
import sqlite3
import datetime
import random
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------- 🔥 웹서버 (포트 유지용) ----------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🌐 Web server running on port {port}")
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ---------- CONFIG ----------
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

DB_PATH = "/data/economy.db" if os.path.exists("/data") else "economy.db"

SALARY_AMOUNT = 100000
SALARY_COOLDOWN = 10
ATTENDANCE_AMOUNT = 500000

# ---------- DB ----------
DB = sqlite3.connect(DB_PATH, check_same_thread=False)
CUR = DB.cursor()

CUR.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
CUR.execute("CREATE TABLE IF NOT EXISTS attendance (uid INTEGER PRIMARY KEY, date TEXT)")
DB.commit()

# ---------- BOT ----------
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

salary_cd = {}

# ---------- UTIL ----------
def money(uid):
    CUR.execute("SELECT bal FROM money WHERE uid=?", (uid,))
    r = CUR.fetchone()
    return r[0] if r else 0

def set_money(uid, v):
    CUR.execute("REPLACE INTO money VALUES (?,?)", (uid, max(v, 0)))
    DB.commit()

def add_money(uid, v):
    set_money(uid, money(uid) + v)

def remove_money(uid, v):
    set_money(uid, money(uid) - v)

def today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")

# ---------- READY ----------
@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        print(f"✅ 로그인: {bot.user}")
    except Exception as e:
        print("❌ 동기화 실패:", e)

# ---------- COMMANDS ----------
@tree.command(name="잔액")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    await interaction.response.send_message(
        f"{user.mention} 잔액: {money(user.id):,}원"
    )

@tree.command(name="출석")
async def attendance(interaction: discord.Interaction):
    CUR.execute("SELECT date FROM attendance WHERE uid=?", (interaction.user.id,))
    r = CUR.fetchone()

    if r and r[0] == today():
        return await interaction.response.send_message("❌ 이미 출석함", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)", (interaction.user.id, today()))
    DB.commit()
    add_money(interaction.user.id, ATTENDANCE_AMOUNT)

    await interaction.response.send_message(f"📅 출석 +{ATTENDANCE_AMOUNT:,}원")

# ---------- RUN ----------
if not TOKEN:
    raise Exception("❌ DISCORD_TOKEN 없음")

while True:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("⚠️ 재시작:", e)
        time.sleep(5)
