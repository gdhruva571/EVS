"""FoodBridge - Flask backend (SQLite by default; set DB_PATH to relocate, see README for MySQL)."""
import os, re, math, random, sqlite3, datetime as dt
from functools import wraps
from flask import Flask, request, jsonify, session, g, render_template
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DB = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "foodbridge.db"))
FMT = "%Y-%m-%dT%H:%M"
now = lambda: dt.datetime.now().strftime(FMT)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
 pw TEXT NOT NULL, role TEXT NOT NULL, phone TEXT, address TEXT, lat REAL, lng REAL, active INTEGER DEFAULT 1, created TEXT);
CREATE TABLE IF NOT EXISTS donations(id INTEGER PRIMARY KEY, rid INTEGER NOT NULL, food TEXT NOT NULL, qty INTEGER NOT NULL,
 prepared TEXT, expiry TEXT NOT NULL, address TEXT, lat REAL, lng REAL, status TEXT DEFAULT 'available', created TEXT);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, did INTEGER NOT NULL, nid INTEGER NOT NULL,
 status TEXT DEFAULT 'pending', note TEXT, created TEXT);
"""

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, a=(), one=False):
    rows = [dict(r) for r in db().execute(sql, a).fetchall()]
    return (rows[0] if rows else None) if one else rows

def ex(sql, a=()):
    c = db().execute(sql, a); db().commit(); return c.lastrowid

def err(m, c=400): return jsonify(error=m), c
def pub(u): return {k: v for k, v in u.items() if k != "pw"}

def cur():
    if "uid" not in session: return None
    return q("SELECT * FROM users WHERE id=? AND active=1", (session["uid"],), True)

def need(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = cur()
            if not u: return err("Please log in first", 401)
            if roles and u["role"] not in roles: return err("You do not have access to this action", 403)
            return f(*a, **k)
        return w
    return deco

def km(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))

@app.get("/")
def index(): return render_template("index.html")

# ---------- auth ----------
@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if d.get("role") not in ("restaurant", "ngo"): return err("Choose restaurant or NGO")
    if len(name) < 2: return err("Name is too short")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email): return err("Enter a valid email")
    if len(pw) < 6: return err("Password must be at least 6 characters")
    try:
        lat, lng = float(d.get("lat")), float(d.get("lng"))
        assert -90 <= lat <= 90 and -180 <= lng <= 180
    except Exception: return err("Enter valid latitude and longitude")
    if q("SELECT 1 FROM users WHERE email=?", (email,), True): return err("Email already registered", 409)
    uid = ex("INSERT INTO users(name,email,pw,role,phone,address,lat,lng,created) VALUES(?,?,?,?,?,?,?,?,?)",
             (name, email, generate_password_hash(pw), d["role"], (d.get("phone") or "")[:20],
              (d.get("address") or "")[:200], lat, lng, now()))
    session["uid"] = uid
    return jsonify(user=pub(q("SELECT * FROM users WHERE id=?", (uid,), True)))

@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    u = q("SELECT * FROM users WHERE email=?", ((d.get("email") or "").strip().lower(),), True)
    if not u or not check_password_hash(u["pw"], d.get("password") or ""): return err("Invalid email or password", 401)
    if not u["active"]: return err("Account suspended. Contact admin.", 403)
    session["uid"] = u["id"]
    return jsonify(user=pub(u))

@app.post("/api/logout")
def logout(): session.clear(); return jsonify(ok=True)

@app.get("/api/me")
def me():
    u = cur(); return jsonify(user=pub(u) if u else None)

# ---------- donations ----------
@app.get("/api/donations")
@need()
def donations():
    u = cur(); sql = "SELECT d.*,u.name rname FROM donations d JOIN users u ON u.id=d.rid WHERE 1=1"; a = []
    if u["role"] == "restaurant": sql += " AND d.rid=?"; a.append(u["id"])
    if u["role"] == "ngo":
        sql += " AND d.status='available' AND d.expiry>?"; a.append(now())
        s = request.args.get("q", "").strip()
        if s: sql += " AND (d.food LIKE ? OR d.address LIKE ? OR u.name LIKE ?)"; a += [f"%{s}%"] * 3
        mq = request.args.get("min_qty", type=int)
        if mq: sql += " AND d.qty>=?"; a.append(mq)
    rows = q(sql + " ORDER BY d.id DESC LIMIT 300", a)
    for r in rows:
        if r["status"] == "available" and r["expiry"] <= now(): r["status"] = "expired"
        if u["role"] == "ngo": r["distance_km"] = round(km(u["lat"], u["lng"], r["lat"], r["lng"]), 1)
    if u["role"] == "ngo": rows.sort(key=lambda r: r["distance_km"])
    return jsonify(rows)

@app.post("/api/donations")
@need("restaurant")
def add_donation():
    u, d = cur(), request.get_json(silent=True) or {}
    food = (d.get("food") or "").strip()
    try: qty = int(d.get("qty"))
    except Exception: return err("Quantity must be a number")
    if len(food) < 2: return err("Enter the food name")
    if not 1 <= qty <= 100000: return err("Quantity must be between 1 and 100000")
    prep, exp = (d.get("prepared") or "")[:16], (d.get("expiry") or "")[:16]
    try: dt.datetime.strptime(prep, FMT); dt.datetime.strptime(exp, FMT)
    except Exception: return err("Enter valid preparation and expiry times")
    if exp <= prep: return err("Expiry must be after preparation time")
    if exp <= now(): return err("Expiry time is already in the past")
    ex("INSERT INTO donations(rid,food,qty,prepared,expiry,address,lat,lng,created) VALUES(?,?,?,?,?,?,?,?,?)",
       (u["id"], food[:100], qty, prep, exp, (d.get("address") or u["address"] or "")[:200], u["lat"], u["lng"], now()))
    return jsonify(ok=True)

@app.post("/api/donations/<int:i>/request")
@need("ngo")
def request_food(i):
    u, d = cur(), q("SELECT * FROM donations WHERE id=?", (i,), True)
    if not d or d["status"] != "available" or d["expiry"] <= now(): return err("This food is no longer available", 409)
    if q("SELECT 1 FROM requests WHERE did=? AND nid=? AND status IN('pending','accepted')", (i, u["id"]), True):
        return err("You already requested this donation", 409)
    ex("INSERT INTO requests(did,nid,created) VALUES(?,?,?)", (i, u["id"], now()))
    return jsonify(ok=True)

@app.get("/api/requests")
@need()
def requests_list():
    u = cur()
    sql = """SELECT r.*,d.food,d.qty,d.address,d.expiry,d.rid,rs.name rname,n.name nname FROM requests r
      JOIN donations d ON d.id=r.did JOIN users rs ON rs.id=d.rid JOIN users n ON n.id=r.nid WHERE 1=1"""
    a = []
    if u["role"] == "restaurant": sql += " AND d.rid=?"; a.append(u["id"])
    if u["role"] == "ngo": sql += " AND r.nid=?"; a.append(u["id"])
    return jsonify(q(sql + " ORDER BY r.id DESC LIMIT 300", a))

@app.post("/api/requests/<int:i>/<act>")
@need("restaurant", "ngo")
def request_action(i, act):
    u = cur()
    r = q("SELECT r.*,d.rid,d.status dstatus FROM requests r JOIN donations d ON d.id=r.did WHERE r.id=?", (i,), True)
    if not r: return err("Request not found", 404)
    owner, mine = u["role"] == "restaurant" and r["rid"] == u["id"], u["role"] == "ngo" and r["nid"] == u["id"]
    if act == "accept" and owner and r["status"] == "pending" and r["dstatus"] == "available":
        ex("UPDATE requests SET status='accepted' WHERE id=?", (i,))
        ex("UPDATE requests SET status='rejected' WHERE did=? AND id!=? AND status='pending'", (r["did"], i))
        ex("UPDATE donations SET status='reserved' WHERE id=?", (r["did"],))
    elif act == "reject" and owner and r["status"] == "pending":
        ex("UPDATE requests SET status='rejected' WHERE id=?", (i,))
    elif act == "collect" and (owner or mine) and r["status"] == "accepted":
        ex("UPDATE requests SET status='collected' WHERE id=?", (i,))
        ex("UPDATE donations SET status='collected' WHERE id=?", (r["did"],))
    elif act == "cancel" and mine and r["status"] in ("pending", "accepted"):
        ex("UPDATE requests SET status='cancelled' WHERE id=?", (i,))
        if r["status"] == "accepted": ex("UPDATE donations SET status='available' WHERE id=?", (r["did"],))
    else: return err("Action not allowed in the current state", 409)
    return jsonify(ok=True)

# ---------- map / stats ----------
@app.get("/api/map")
def map_data():
    users = q("SELECT id,name,role,address,lat,lng FROM users WHERE active=1 AND role IN('restaurant','ngo')")
    dons = q("""SELECT d.id,d.food,d.qty,d.expiry,d.lat,d.lng,u.name rname FROM donations d JOIN users u ON u.id=d.rid
                WHERE d.status='available' AND d.expiry>?""", (now(),))
    return jsonify(restaurants=[x for x in users if x["role"] == "restaurant"],
                   ngos=[x for x in users if x["role"] == "ngo"], donations=dons)

KG_PER_SERVING, CO2_PER_KG = 0.4, 2.5  # rough planning assumptions, shown in the UI

@app.get("/api/stats")
def stats():
    one = lambda s: q(s, (), True)
    donated = one("SELECT COALESCE(SUM(qty),0) n FROM donations WHERE status='collected'")["n"]
    kg = round(donated * KG_PER_SERVING)
    return jsonify(donated=donated, waste_kg=kg, co2_kg=round(kg * CO2_PER_KG),
        restaurants=one("SELECT COUNT(*) n FROM users WHERE role='restaurant' AND active=1")["n"],
        ngos=one("SELECT COUNT(*) n FROM users WHERE role='ngo' AND active=1")["n"],
        monthly=list(reversed(q("""SELECT substr(created,1,7) m,SUM(qty) listed,
            SUM(CASE WHEN status='collected' THEN qty ELSE 0 END) donated FROM donations GROUP BY m ORDER BY m DESC LIMIT 6"""))),
        status=q("SELECT status,COUNT(*) n FROM donations GROUP BY status"))

# ---------- AI / analytics (statistical demo, not a trained model) ----------
@app.get("/api/ml")
def ml():
    today = dt.date.today()
    rows = q("SELECT substr(created,1,10) d,SUM(qty) s FROM donations WHERE created>=? GROUP BY d",
             ((today - dt.timedelta(days=90)).isoformat(),))
    daily = {r["d"]: r["s"] for r in rows}
    meta = dict(label="DEMO PREDICTION", method="Weekday-average baseline scaled by 14-day trend. A statistical heuristic, "
                "not a trained machine-learning model; accuracy is not validated.")
    if len(daily) < 14: return jsonify(**meta, insufficient=True)
    days = [today - dt.timedelta(days=i) for i in range(89, -1, -1)]
    vals = [daily.get(d.isoformat(), 0) for d in days]
    wd = {w: [v for d, v in zip(days, vals) if d.weekday() == w] for w in range(7)}
    avg = {w: sum(x) / len(x) for w, x in wd.items()}
    trend = min(1.5, max(0.5, (sum(vals[-14:]) / 14) / max(sum(vals) / 90, 1)))
    fc = [{"date": (today + dt.timedelta(days=i)).isoformat(),
           "qty": round(avg[(today + dt.timedelta(days=i)).weekday()] * trend)} for i in range(1, 8)]
    last30 = q("""SELECT COALESCE(SUM(qty),0) l,COALESCE(SUM(CASE WHEN status='collected' THEN qty ELSE 0 END),0) c
                  FROM donations WHERE created>=?""", ((today - dt.timedelta(days=30)).isoformat(),), True)
    return jsonify(**meta, history=[{"date": d.isoformat(), "qty": v} for d, v in zip(days[-14:], vals[-14:])], forecast=fc,
        trend=round(trend, 2), demand_per_day=round(last30["c"] / 30), sell_through=round(100 * last30["c"] / max(last30["l"], 1)))

@app.get("/api/recommend/<int:i>")
@need("restaurant", "admin")
def recommend(i):
    d = q("SELECT * FROM donations WHERE id=?", (i,), True)
    if not d: return err("Donation not found", 404)
    out = []
    for n in q("SELECT * FROM users WHERE role='ngo' AND active=1"):
        dist = km(d["lat"], d["lng"], n["lat"], n["lng"])
        load = q("SELECT COUNT(*) c FROM requests WHERE nid=? AND status IN('pending','accepted')", (n["id"],), True)["c"]
        score = 0.7 * max(0, 1 - dist / 15) + 0.3 / (1 + load)
        out.append(dict(id=n["id"], name=n["name"], address=n["address"], distance_km=round(dist, 1), open_requests=load, score=round(score * 100)))
    return jsonify(label="DEMO RECOMMENDATION", method="Rule-based score: 70% proximity + 30% NGO workload.",
                   ngos=sorted(out, key=lambda x: -x["score"])[:3])

# ---------- admin ----------
@app.get("/api/users")
@need("admin")
def users(): return jsonify([pub(u) for u in q("SELECT * FROM users ORDER BY id DESC")])

@app.post("/api/users/<int:i>/toggle")
@need("admin")
def toggle(i):
    u = q("SELECT * FROM users WHERE id=?", (i,), True)
    if not u or u["role"] == "admin": return err("Cannot change this account", 403)
    ex("UPDATE users SET active=? WHERE id=?", (0 if u["active"] else 1, i))
    return jsonify(ok=True)

# ---------- database init + demo data ----------
def init():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]: return c.close()
    rnd, h, T = random.Random(7), generate_password_hash("demo123"), dt.datetime.now()
    f = lambda t: t.strftime(FMT)
    def user(n, e, r, a, lat, lng, pw=h):
        return c.execute("INSERT INTO users(name,email,pw,role,phone,address,lat,lng,created) VALUES(?,?,?,?,?,?,?,?,?)",
                         (n, e, pw, r, "+91 90000 0%04d" % rnd.randint(0, 9999), a, lat, lng, f(T))).lastrowid
    user("Admin", "admin@foodbridge.test", "admin", "HQ", 12.97, 77.59, generate_password_hash("admin123"))
    R = [("Green Leaf Kitchen", 12.9716, 77.5946, "MG Road"), ("Spice Route", 12.9352, 77.6245, "Koramangala"),
         ("Urban Tandoor", 12.9784, 77.6408, "Indiranagar"), ("Coastal Catch", 12.9141, 77.6101, "HSR Layout"),
         ("Bread & Co", 13.0070, 77.5700, "Malleshwaram"), ("Curry Leaf", 12.9250, 77.5938, "Jayanagar")]
    N = [("Annapurna Trust", 12.9600, 77.5800, "Shanthinagar"), ("Hope Kitchen", 12.9900, 77.6200, "Ulsoor"),
         ("Seva Foundation", 12.9300, 77.6500, "Bellandur"), ("Care Hands", 13.0100, 77.5500, "Rajajinagar")]
    rid = [user(n, "%s@demo.test" % n.split()[0].lower().replace("&", "bread"), "restaurant", a, la, lo) for n, la, lo, a in R]
    nid = [user(n, "%s@demo.test" % n.split()[0].lower(), "ngo", a, la, lo) for n, la, lo, a in N]
    foods = ["Veg biryani", "Dal & rice", "Chapati & curry", "Fresh bread loaves", "Pasta trays", "Idli & sambar", "Fried rice", "Sandwich boxes"]
    def don(r, food, qty, created, exp, status):
        u = R[rid.index(r)]
        return c.execute("INSERT INTO donations(rid,food,qty,prepared,expiry,address,lat,lng,status,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (r, food, qty, f(created - dt.timedelta(hours=2)), f(exp), u[3], u[1], u[2], status, f(created))).lastrowid
    def req(d, n, s, t): c.execute("INSERT INTO requests(did,nid,status,created) VALUES(?,?,?,?)", (d, n, s, f(t)))
    for day in range(180, 0, -1):
        t0 = T - dt.timedelta(days=day)
        for _ in range(rnd.choice([0, 1, 1, 2])):
            t = t0.replace(hour=rnd.randint(12, 22))
            qty = int(rnd.randint(10, 70) * (1.35 if t.weekday() >= 4 else 1) * (1 + (180 - day) / 600))
            s = rnd.choices(["collected", "expired", "cancelled"], [82, 12, 6])[0]
            d = don(rnd.choice(rid), rnd.choice(foods), qty, t, t + dt.timedelta(hours=5), s)
            if s == "collected": req(d, rnd.choice(nid), "collected", t + dt.timedelta(minutes=20))
    for i, (r, food, qty, h_) in enumerate([(rid[0], "Veg biryani", 40, 5), (rid[1], "Dal & rice", 55, 6), (rid[2], "Chapati & curry", 30, 4),
                                            (rid[4], "Fresh bread loaves", 25, 8), (rid[3], "Fried rice", 35, 7)]):
        d = don(r, food, qty, T - dt.timedelta(minutes=30), T + dt.timedelta(hours=h_), "available")
        if i == 0: req(d, nid[0], "pending", T)
        if i == 4:
            req(d, nid[1], "accepted", T); c.execute("UPDATE donations SET status='reserved' WHERE id=?", (d,))
    c.commit(); c.close()

init()
if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
