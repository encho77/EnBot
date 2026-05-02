import discord
from discord import app_commands
import sqlite3
import datetime
import random
import os

# ---------- DB ----------
DB = sqlite3.connect("economy.db")
CUR = DB.cursor()

CUR.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
CUR.execute("CREATE TABLE IF NOT EXISTS attendance (uid INTEGER PRIMARY KEY, date TEXT)")
DB.commit()

# ---------- CONFIG ----------
SALARY_AMOUNT = 100000
SALARY_COOLDOWN = 10
ATTENDANCE_AMOUNT = 500000

salary_cd = {}

# ---------- BOT ----------
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

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
    await tree.sync()
    print(f"✅ 로그인됨: {bot.user}")

# ---------- BALANCE ----------
@tree.command(name="잔액", description="잔액 확인")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user

    embed = discord.Embed(
        title="💰 잔액 확인",
        description=f"{user.mention}\n잔액: `{money(user.id):,}원`",
        color=0x2ecc71
    )
    await interaction.response.send_message(embed=embed)

# ---------- TRANSFER ----------
@tree.command(name="송금", description="유저에게 돈 보내기")
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
        description=f"{interaction.user.mention} → {user.mention}\n금액: `{amount:,}원`",
        color=0x3498db
    )
    await interaction.response.send_message(embed=embed)

# ---------- ATTENDANCE ----------
@tree.command(name="출석", description="하루 1회 출석 보상")
async def attendance(interaction: discord.Interaction):

    CUR.execute("SELECT date FROM attendance WHERE uid=?", (interaction.user.id,))
    r = CUR.fetchone()

    if r and r[0] == today():
        return await interaction.response.send_message("❌ 오늘 이미 출석했습니다", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)", (interaction.user.id, today()))
    DB.commit()

    add_money(interaction.user.id, ATTENDANCE_AMOUNT)

    embed = discord.Embed(
        title="📅 출석 완료",
        description=f"보상: `{ATTENDANCE_AMOUNT:,}원`",
        color=0x57f287
    )
    await interaction.response.send_message(embed=embed)

# ---------- SALARY ----------
@tree.command(name="월급", description="쿨타임 있는 월급")
async def salary(interaction: discord.Interaction):

    now = datetime.datetime.utcnow().timestamp()
    last = salary_cd.get(interaction.user.id, 0)

    if now - last < SALARY_COOLDOWN:
        return await interaction.response.send_message("⏳ 쿨타임 중", ephemeral=True)

    salary_cd[interaction.user.id] = now
    add_money(interaction.user.id, SALARY_AMOUNT)

    embed = discord.Embed(
        title="💼 월급 지급",
        description=f"+{SALARY_AMOUNT:,}원 지급",
        color=0x9b59b6
    )
    await interaction.response.send_message(embed=embed)

# ---------- ODD / EVEN ----------
@tree.command(name="홀짝", description="홀짝 게임")
@app_commands.describe(choice="홀 또는 짝", bet="배팅 금액")
async def odd_even(interaction: discord.Interaction, choice: str, bet: int):

    if choice not in ["홀", "짝"]:
        return await interaction.response.send_message("❌ '홀' 또는 '짝'만 입력", ephemeral=True)

    if bet <= 0:
        return await interaction.response.send_message("❌ 금액 오류", ephemeral=True)

    if money(interaction.user.id) < bet:
        return await interaction.response.send_message("❌ 잔액 부족", ephemeral=True)

    num = random.randint(1, 100)
    result = "홀" if num % 2 else "짝"

    if choice == result:
        reward = bet * 2
        add_money(interaction.user.id, reward)
        text = f"🎉 승리!\n숫자: {num} ({result})\n+{reward:,}원"
    else:
        remove_money(interaction.user.id, bet)
        text = f"💥 패배!\n숫자: {num} ({result})\n-{bet:,}원"

    embed = discord.Embed(
        title="🎲 홀짝 게임",
        description=text,
        color=0xf1c40f
    )
    await interaction.response.send_message(embed=embed)

# ---------- RUN ----------
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
