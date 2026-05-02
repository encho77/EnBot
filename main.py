# ================= ECONOMY SYSTEM =================

import datetime
import random

# ---------- DB ----------
CUR.execute("CREATE TABLE IF NOT EXISTS money (uid INTEGER PRIMARY KEY, bal INTEGER)")
CUR.execute("CREATE TABLE IF NOT EXISTS attendance (uid INTEGER PRIMARY KEY, date TEXT)")
DB.commit()

# ---------- CONFIG ----------
SALARY_AMOUNT = 100000
SALARY_COOLDOWN = 10
ATTENDANCE_AMOUNT = 500000

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

# ---------- BALANCE ----------
@bot.tree.command(name="잔액")
async def balance(i: discord.Interaction, user: discord.Member = None):
    user = user or i.user

    await i.response.send_message(
        embed=discord.Embed(
            title="💰 잔액 확인",
            description=f"{user.mention}\n잔액: `{money(user.id):,}원`",
            color=0x2ecc71
        )
    )

# ---------- TRANSFER ----------
@bot.tree.command(name="송금")
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
        embed=discord.Embed(
            title="💸 송금 완료",
            description=f"{i.user.mention} → {user.mention}\n금액: `{amount:,}원`",
            color=0x3498db
        )
    )

# ---------- ATTENDANCE ----------
@bot.tree.command(name="출석")
async def attendance(i: discord.Interaction):

    CUR.execute("SELECT date FROM attendance WHERE uid=?", (i.user.id,))
    r = CUR.fetchone()

    if r and r[0] == today():
        return await i.response.send_message("❌ 오늘 이미 출석했습니다", ephemeral=True)

    CUR.execute("REPLACE INTO attendance VALUES (?,?)", (i.user.id, today()))
    DB.commit()

    add_money(i.user.id, ATTENDANCE_AMOUNT)

    await i.response.send_message(
        embed=discord.Embed(
            title="📅 출석 완료",
            description=f"보상: `{ATTENDANCE_AMOUNT:,}원`",
            color=0x57f287
        )
    )

# ---------- SALARY ----------
@bot.tree.command(name="월급")
async def salary(i: discord.Interaction):

    now = datetime.datetime.utcnow().timestamp()
    last = salary_cd.get(i.user.id, 0)

    if now - last < SALARY_COOLDOWN:
        return await i.response.send_message("⏳ 쿨타임 중", ephemeral=True)

    salary_cd[i.user.id] = now
    add_money(i.user.id, SALARY_AMOUNT)

    await i.response.send_message(
        embed=discord.Embed(
            title="💼 월급 지급",
            description=f"+{SALARY_AMOUNT:,}원 지급",
            color=0x9b59b6
        )
    )

# ---------- ODD / EVEN GAME ----------
@bot.tree.command(name="홀짝")
async def odd_even(i: discord.Interaction, choice: str, bet: int):

    if bet <= 0:
        return await i.response.send_message("❌ 금액 오류", ephemeral=True)

    if money(i.user.id) < bet:
        return await i.response.send_message("❌ 잔액 부족", ephemeral=True)

    num = random.randint(1, 100)
    result = "홀" if num % 2 else "짝"

    win = (choice == result)

    if win:
        reward = bet * 2
        add_money(i.user.id, reward)
        text = f"🎉 승리!\n숫자: {num} ({result})\n+{reward:,}원"
    else:
        remove_money(i.user.id, bet)
        text = f"💥 패배!\n숫자: {num} ({result})\n-{bet:,}원"

    await i.response.send_message(
        embed=discord.Embed(
            title="🎲 홀짝 게임",
            description=text,
            color=0xf1c40f
        )
                                            )
