# ================== IMPORT ==================
import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import datetime
import random
import time
from flask import Flask, jsonify
from threading import Thread

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== DB ==================
DB = sqlite3.connect("bot.db", check_same_thread=False)
CUR = DB.cursor()

CUR.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
CUR.execute("CREATE TABLE IF NOT EXISTS attendance (uid INTEGER PRIMARY KEY, date TEXT)")
DB.commit()

# ================== KEEP ALIVE - Render 최적화 ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "Quabot Economy System - ONLINE"

@app.route("/ping")
def ping():
    return jsonify({
        "status": "alive",
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "service": "quabot"
    })

@app.route("/health")
def health():
    return "OK", 200

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Keep-Alive Server Started on port {port}")
    Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    ).start()

# ================== ECONOMY CONFIG ==================
SALARY_AMOUNT = 100000
SALARY_COOLDOWN = 10      # 초 단위
ATTENDANCE_AMOUNT = 500000

salary_cd = {}

# ================== ECONOMY FUNCTIONS ==================
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

# ================== COMMANDS ==================

@bot.tree.command(name="잔액", description="잔액을 확인합니다.")
async def balance(i: discord.Interaction, user: discord.Member = None):
    user = user or i.user
    await i.response.send_message(
        embed=discord.Embed(
            title="💰 잔액 확인",
            description=f"{user.mention}\n**잔액**: `{money(user.id):,}원`",
            color=0x2ecc71
        )
    )

@bot.tree.command(name="송금", description="다른 유저에게 돈을 송금합니다.")
async def transfer(i: discord.Interaction, user: discord.Member, amount: int):
    if user.bot or user.id == i.user.id:
        return await i.response.send_message("❌ 자신에게는 송금할 수 없습니다.", ephemeral=True)
    if amount <= 0:
        return await i.response.send_message("❌ 1원 이상만 송금 가능합니다.", ephemeral=True)
    if money(i.user.id) < amount:
        return await i.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)

    remove_money(i.user.id, amount)
    add_money(user.id, amount)

    await i.response.send_message(
        embed=discord.Embed(
            title="💸 송금 완료",
            description=f"{i.user.mention} → {user.mention}\n**금액**: `{amount:,}원`",
            color=0x3498db
        )
    )

@bot.tree.command(name="출석", description="매일 출석 체크하고 보상을 받습니다.")
async def attendance(i: discord.Interaction):
    CUR.execute("SELECT date FROM attendance WHERE uid=?", (i.user.id,))
    r = CUR.fetchone()

    if r and r[0] == today():
        return await i.response.send_message("❌ 오늘 이미 출석하셨습니다.", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)", (i.user.id, today()))
    DB.commit()
    add_money(i.user.id, ATTENDANCE_AMOUNT)

    await i.response.send_message(
        embed=discord.Embed(
            title="📅 출석 완료!",
            description=f"`{ATTENDANCE_AMOUNT:,}원`이 지급되었습니다!",
            color=0x57f287
        )
    )

@bot.tree.command(name="월급", description="월급을 받습니다. (쿨타임 10초)")
async def salary(i: discord.Interaction):
    now = datetime.datetime.utcnow().timestamp()
    last = salary_cd.get(i.user.id, 0)

    if now - last < SALARY_COOLDOWN:
        remain = int(SALARY_COOLDOWN - (now - last))
        return await i.response.send_message(f"⏳ {remain}초 후에 다시 받을 수 있습니다.", ephemeral=True)

    salary_cd[i.user.id] = now
    add_money(i.user.id, SALARY_AMOUNT)

    await i.response.send_message(
        embed=discord.Embed(
            title="💼 월급 지급",
            description=f"`{SALARY_AMOUNT:,}원`이 지급되었습니다!",
            color=0x9b59b6
        )
    )

@bot.tree.command(name="홀짝", description="홀짝 게임으로 돈을 벌어보세요!")
async def odd_even(i: discord.Interaction, choice: str, bet: int):
    if bet <= 0:
        return await i.response.send_message("❌ 베팅 금액은 1원 이상이어야 합니다.", ephemeral=True)
    if money(i.user.id) < bet:
        return await i.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)

    num = random.randint(1, 100)
    result = "홀" if num % 2 == 1 else "짝"
    win = (choice.lower() == result)

    if win:
        reward = bet * 2
        add_money(i.user.id, reward)
        text = f"🎉 **승리!**\n숫자: `{num}` ({result})\n`+{reward:,}원`"
        color = 0x2ecc71
    else:
        remove_money(i.user.id, bet)
        text = f"💥 **패배...**\n숫자: `{num}` ({result})\n`- {bet:,}원`"
        color = 0xe74c3c

    await i.response.send_message(
        embed=discord.Embed(title="🎲 홀짝 게임", description=text, color=color)
    )

# ================== ON_READY ==================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ {bot.user} 로그인 완료 | Render 경제 시스템 작동 중")

# ================== 실행 ==================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
