from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import bcrypt
import jwt
import json
import os
from datetime import datetime, timedelta

app = FastAPI(title="TourStat KG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "tourstat-kg-secret-change-in-production")
JWT_EXPIRE_HOURS = 24
DB_PATH = "db.json"
bearer = HTTPBearer()

# ============================================================
# DB LAYER — сейчас JSON файл
# Чтобы перейти на PostgreSQL — замени только функции ниже.
# Например: pip install asyncpg databases
# и замени read_db/write_db на SQL запросы.
# Всё остальное (роуты, логика) трогать не нужно.
# ============================================================

def read_db() -> dict:
    if not os.path.exists(DB_PATH):
        initial = {"users": []}
        write_db(initial)
        return initial
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def write_db(data: dict):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- USER QUERIES ---
# PostgreSQL замена: SELECT * FROM users WHERE email=$1

def find_user_by_email(email: str) -> Optional[dict]:
    db = read_db()
    return next((u for u in db["users"] if u["email"] == email), None)

def find_user_by_id(user_id: str) -> Optional[dict]:
    db = read_db()
    return next((u for u in db["users"] if u["id"] == user_id), None)

def create_user(email: str, password: str, role: str, company: str) -> dict:
    db = read_db()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = {
        "id": str(int(datetime.utcnow().timestamp() * 1000)),
        "email": email,
        "password_hash": hashed,
        "role": role,
        "company": company,
        "plan": "basic" if role == "client" else None,
        "created_at": datetime.utcnow().isoformat(),
    }
    db["users"].append(user)
    write_db(db)
    return user

def get_all_users() -> list:
    db = read_db()
    return [{k: v for k, v in u.items() if k != "password_hash"} for u in db["users"]]

def delete_user(user_id: str):
    db = read_db()
    db["users"] = [u for u in db["users"] if u["id"] != user_id]
    write_db(db)

# ============================================================
# JWT
# ============================================================

def create_token(user: dict) -> str:
    payload = {
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "company": user["company"],
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истёк")
    except Exception:
        raise HTTPException(status_code=401, detail="Токен недействителен")

def require_admin(user: dict = Depends(verify_token)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Только для администраторов")
    return user

# ============================================================
# TOURIST DATA — демо, потом переедет в таблицу tourist_stats
# ============================================================

TOURIST_DATA = {
    "total_now": 14820,
    "change_percent": 12.4,
    "by_country": [
        {"country": "Казахстан",      "count": 4200, "flag": "🇰🇿"},
        {"country": "Россия",         "count": 3800, "flag": "🇷🇺"},
        {"country": "Китай",          "count": 2100, "flag": "🇨🇳"},
        {"country": "Германия",       "count": 980,  "flag": "🇩🇪"},
        {"country": "США",            "count": 870,  "flag": "🇺🇸"},
        {"country": "Великобритания", "count": 650,  "flag": "🇬🇧"},
        {"country": "Узбекистан",     "count": 580,  "flag": "🇺🇿"},
        {"country": "Другие",         "count": 1640, "flag": "🌍"},
    ],
    "by_region": [
        {"region": "Иссык-Куль", "count": 6200, "percent": 42},
        {"region": "Бишкек",     "count": 3800, "percent": 26},
        {"region": "Ош",         "count": 1900, "percent": 13},
        {"region": "Чуй",        "count": 1100, "percent": 7},
        {"region": "Нарын",      "count": 890,  "percent": 6},
        {"region": "Талас",      "count": 490,  "percent": 3},
        {"region": "Баткен",     "count": 440,  "percent": 3},
    ],
    "monthly": [
        {"month": "Янв", "tourists": 2100},  {"month": "Фев", "tourists": 1800},
        {"month": "Мар", "tourists": 3200},  {"month": "Апр", "tourists": 4500},
        {"month": "Май", "tourists": 7800},  {"month": "Июн", "tourists": 12400},
        {"month": "Июл", "tourists": 18900}, {"month": "Авг", "tourists": 16700},
        {"month": "Сен", "tourists": 9800},  {"month": "Окт", "tourists": 5400},
        {"month": "Ноя", "tourists": 2900},  {"month": "Дек", "tourists": 1900},
    ],
    "top_locations": [
        {"name": "Иссык-Куль", "visitors": 6200, "trend": "+18%", "lat": 42.49, "lng": 77.39},
        {"name": "Ала-Арча",   "visitors": 2800, "trend": "+24%", "lat": 42.56, "lng": 74.49},
        {"name": "Каракол",    "visitors": 1900, "trend": "+9%",  "lat": 42.49, "lng": 78.38},
        {"name": "Таш-Рабат",  "visitors": 980,  "trend": "+31%", "lat": 40.83, "lng": 75.24},
        {"name": "Узген",      "visitors": 760,  "trend": "+5%",  "lat": 40.77, "lng": 73.30},
        {"name": "Арсланбоб",  "visitors": 640,  "trend": "+42%", "lat": 41.35, "lng": 72.93},
    ],
    "stats_summary": {
        "avg_stay_days": 7.3,
        "avg_spend_usd": 420,
        "repeat_visitors_percent": 28,
        "total_revenue_est_mln": 6.2,
    }
}

# ============================================================
# SCHEMAS
# ============================================================

class LoginRequest(BaseModel):
    email: str
    password: str

class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "client"
    company: str = ""

# ============================================================
# AUTH ROUTES
# ============================================================

@app.post("/api/auth/login")
def login(body: LoginRequest):
    email = body.email.lower().strip()
    user = find_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    token = create_token(user)
    return {
        "success": True,
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "role": user["role"],
                 "company": user["company"], "plan": user["plan"]}
    }

@app.get("/api/auth/me")
def me(current: dict = Depends(verify_token)):
    user = find_user_by_id(current["id"])
    if not user:
        raise HTTPException(status_code=404, detail="Не найден")
    return {"success": True, "user": {"id": user["id"], "email": user["email"],
            "role": user["role"], "company": user["company"], "plan": user["plan"]}}

# ============================================================
# ADMIN ROUTES
# ============================================================

@app.get("/api/admin/users")
def list_users(admin: dict = Depends(require_admin)):
    return {"success": True, "data": get_all_users()}

@app.post("/api/admin/users")
def add_user(body: CreateUserRequest, admin: dict = Depends(require_admin)):
    email = body.email.lower().strip()
    if find_user_by_email(email):
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    user = create_user(email, body.password, body.role, body.company)
    return {"success": True, "user": {"id": user["id"], "email": user["email"],
            "role": user["role"], "company": user["company"]}}

@app.delete("/api/admin/users/{user_id}")
def remove_user(user_id: str, admin: dict = Depends(require_admin)):
    delete_user(user_id)
    return {"success": True}

# ============================================================
# STATS ROUTES
# ============================================================

@app.get("/api/stats")
def stats(current: dict = Depends(verify_token)):
    return {"success": True, "data": TOURIST_DATA}

@app.get("/api/regions")
def regions(current: dict = Depends(verify_token)):
    return {"success": True, "data": TOURIST_DATA["by_region"]}

@app.get("/api/countries")
def countries(current: dict = Depends(verify_token)):
    return {"success": True, "data": TOURIST_DATA["by_country"]}

@app.get("/api/locations")
def locations(current: dict = Depends(verify_token)):
    return {"success": True, "data": TOURIST_DATA["top_locations"]}

@app.get("/api/monthly")
def monthly(current: dict = Depends(verify_token)):
    return {"success": True, "data": TOURIST_DATA["monthly"]}

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# ============================================================
# SEED — первый админ при старте
# ============================================================

def seed_admin():
    db = read_db()
    if not any(u["role"] == "admin" for u in db["users"]):
        create_user("admin@tourstat.kg", "Admin1234!", "admin", "TourStat KG")
        print("\n👤 Создан администратор:")
        print("   Email:  admin@tourstat.kg")
        print("   Пароль: Admin1234!")
        print("   ⚠️  Смените пароль в продакшне!\n")

seed_admin()

# ============================================================
# ЗАПУСК
# ============================================================
# python main.py
# ИЛИ
# uvicorn main:app --reload --port 3001

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3001, reload=True)
