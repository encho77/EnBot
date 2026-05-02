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
    CUR.execute("SELECT bal FROM m
