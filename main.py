import discord
from discord import app_commands
import sqlite3
import datetime
import random
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------- 🌐 WEB SERVER (포트 유지) ----------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🌐 Port {port} opened")
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

def embed(title, desc, color=0x5865F2):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="💸 Economy Bot")
    return e

# ---------- READY ----------
@bot.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        print(f"✅ 로그인 완료: {bot.user}")
    except Exception as e:
        print("❌ 동기화 실패:", e)

# ---------- COMMANDS ----------

# 💰 잔액
@tree.command(name="잔액", description="잔액 확인")
async def balance(i: discord.Interaction, user: discord.Member = None):
    user = user or i.user
    await i.response.send_message(
        embed=embed("💰 잔액", f"{user.mention}\n`{money(user.id):,}원`", 0x2ecc71)
    )

# 💸 송금
@tree.command(name="송금", description="돈 보내기")
async def transfer(i: discord.Interaction, user: discord.Member, amount: int):
    if user.bot or user.id == i.user.id:
        return await i.response.send_message("❌ 대상 오류", ephemeral=True)

    if amount <= 0:
        return await i.response.send_message("❌ 금액 오류", ephemeral=True)

    if money(i.user.id) < amount:
        return await i.response.send_message("❌ 잔액 부족", ephemeral=True)

    remove_money(i.user.id, amount)
    add_money(user.id, amount)

    await i.response.send_message(
        embed=embed("💸 송금 완료",
        f"{i.user.mention} → {user.mention}\n`{amount:,}원`", 0x3498db)
    )

# 📅 출석
@tree.command(name="출석", description="하루 1회 보상")
async def attendance(i: discord.Interaction):
    CUR.execute("SELECT date FROM attendance WHERE uid=?", (i.user.id,))
    r = CUR.fetchone()

    if r and r[0] == today():
        return await i.response.send_message("❌ 이미 출석함", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)", (i.user.id, today()))
    DB.commit()
    add_money(i.user.id, ATTENDANCE_AMOUNT)

    await i.response.send_message(
        embed=embed("📅 출석 완료", f"+{ATTENDANCE_AMOUNT:,}원", 0x57f287)
    )

# 💼 월급
@tree.command(name="월급", description="쿨타임 월급")
async def salary(i: discord.Interaction):
    now = datetime.datetime.utcnow().timestamp()
    last = salary_cd.get(i.user.id, 0)

    if now - last < SALARY_COOLDOWN:
        return await i.response.send_message("⏳ 쿨타임", ephemeral=True)

    salary_cd[i.user.id] = now
    add_money(i.user.id, SALARY_AMOUNT)

    await i.response.send_message(
        embed=embed("💼 월급 지급", f"+{SALARY_AMOUNT:,}원", 0x9b59b6)
    )

# 🎲 홀짝
@tree.command(name="홀짝", description="홀짝 게임")
@app_commands.describe(choice="홀 또는 짝", bet="배팅 금액")
async def odd_even(i: discord.Interaction, choice: str, bet: int):

    if choice not in ["홀", "짝"]:
        return await i.response.send_message("❌ 홀/짝만 가능", ephemeral=True)

    if bet <= 0:
        return await i.response.send_message("❌ 금액 오류", ephemeral=True)

    if money(i.user.id) < bet:
        return await i.response.send_message("❌ 잔액 부족", ephemeral=True)

    num = random.randint(1, 100)
    result = "홀" if num % 2 else "짝"

    if choice == result:
        reward = bet * 2
        add_money(i.user.id, reward)
        msg = f"🎉 승리!\n숫자: {num} ({result})\n+{reward:,}원"
    else:
        remove_money(i.user.id, bet)
        msg = f"💥 패배!\n숫자: {num} ({result})\n-{bet:,}원"

    await i.response.send_message(
        embed=embed("🎲 홀짝 결과", msg, 0xf1c40f)
    )

# ---------- RUN ----------
if not TOKEN:
    raise Exception("❌ DISCORD_TOKEN 없음")

while True:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("⚠️ 재시작:", e)
        time.sleep(5)
