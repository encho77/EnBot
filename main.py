import discord
from discord import app_commands
import sqlite3
import datetime
import random
import os
import time
from flask import Flask
from threading import Thread

# ---------- WEB SERVER ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web).start()

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
@tree.command(name="잔액", description="잔액 확인")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user

    embed = discord.Embed(
        title="💰 잔액",
        description=f"{user.mention}\n`{money(user.id):,}원`",
        color=0x2ecc71
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="송금", description="송금")
async def transfer(interaction: discord.Interaction, user: discord.Member, amount: int):

    if user.bot or user.id == interaction.user.id:
        return await interaction.response.send_message("❌ 대상 오류", ephemeral=True)

    if amount <= 0:
        return await interaction.response.send_message("❌ 금액 오류", ephemeral=True)

    if money(interaction.user.id) < amount:
        return await interaction.response.send_message("❌ 잔액 부족", ephemeral=True)

    remove_money(interaction.user.id, amount)
    add_money(user.id, amount)

    embed = discord.Embed(
        title="💸 송금 완료",
        description=f"{interaction.user.mention} → {user.mention}\n`{amount:,}원`",
        color=0x3498db
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="출석", description="출석 체크")
async def attendance(interaction: discord.Interaction):

    CUR.execute("SELECT date FROM attendance WHERE uid=?", (interaction.user.id,))
    r = CUR.fetchone()

    if r and r[0] == today():
        return await interaction.response.send_message("❌ 이미 출석함", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)", (interaction.user.id, today()))
    DB.commit()

    add_money(interaction.user.id, ATTENDANCE_AMOUNT)

    embed = discord.Embed(
        title="📅 출석 완료",
        description=f"+{ATTENDANCE_AMOUNT:,}원",
        color=0x57f287
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="월급", description="월급 받기")
async def salary(interaction: discord.Interaction):

    now = datetime.datetime.utcnow().timestamp()
    last = salary_cd.get(interaction.user.id, 0)

    if now - last < SALARY_COOLDOWN:
        return await interaction.response.send_message("⏳ 쿨타임", ephemeral=True)

    salary_cd[interaction.user.id] = now
    add_money(interaction.user.id, SALARY_AMOUNT)

    embed = discord.Embed(
        title="💼 월급",
        description=f"+{SALARY_AMOUNT:,}원",
        color=0x9b59b6
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="홀짝", description="홀짝 게임")
@app_commands.describe(choice="홀 또는 짝", bet="배팅 금액")
async def odd_even(interaction: discord.Interaction, choice: str, bet: int):

    if choice not in ["홀", "짝"]:
        return await interaction.response.send_message("❌ 홀/짝만 가능", ephemeral=True)

    if bet <= 0:
        return await interaction.response.send_message("❌ 금액 오류", ephemeral=True)

    if money(interaction.user.id) < bet:
        return await interaction.response.send_message("❌ 잔액 부족", ephemeral=True)

    num = random.randint(1, 100)
    result = "홀" if num % 2 else "짝"

    if choice == result:
        reward = bet * 2
        add_money(interaction.user.id, reward)
        text = f"🎉 승리\n{num} ({result})\n+{reward:,}원"
    else:
        remove_money(interaction.user.id, bet)
        text = f"💥 패배\n{num} ({result})\n-{bet:,}원"

    embed = discord.Embed(title="🎲 결과", description=text, color=0xf1c40f)
    await interaction.response.send_message(embed=embed)

# ---------- RUN ----------
if not TOKEN:
    raise Exception("❌ DISCORD_TOKEN 없음")

while True:
    try:
        bot.run(TOKEN)
    except Exception as e:
        print("⚠️ 재시작:", e)
        time.sleep(5)
