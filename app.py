import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
import yfinance as yf

app = Flask(__name__)
app.secret_key = "super_secret_market_key"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_PASSWORD = "admin1234"

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_vip INTEGER DEFAULT 0,
            slip_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def calculate_fear_greed():
    try:
        vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
        sp500 = yf.Ticker("^GSPC").history(period="100d")
        current_sp = sp500['Close'].iloc[-1]
        ema50 = sp500['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        vix_score = max(0, min(100, (vix - 10) * 2.5))
        distance = ((current_sp - ema50) / ema50) * 100
        distance_score = max(0, min(100, 50 + (distance * 10)))
        score = int((vix_score + (100 - distance_score)) / 2)
        return max(0, min(100, score))
    except:
        return 50

def get_vip_stocks():
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    results = []
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="30d")
            close = hist['Close'].iloc[-1]
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
            rs = gain / (loss if loss != 0 else 1)
            rsi = int(100 - (100 / (1 + rs)))
            tp = round(close * 1.10, 2)
            sl = round(close * 0.95, 2)
            results.append({"ticker": t, "price": round(close, 2), "rsi": rsi, "tp": tp, "sl": sl})
        except:
            continue
    return results

@app.route('/')
def index():
    score = calculate_fear_greed()
    if score < 30:
        signal, color, text = "EXTREME FEAR", "success", "ตลาดกลัวจัด! โอกาสทำกำไรสูงมาก ช้อนซื้อได้เลย"
    elif score > 70:
        signal, color, text = "EXTREME GREED", "danger", "ตลาดโลภจัด! ความเสี่ยงดอยสูง แนะนำถือเงินสดไว้ก่อน"
    else:
        signal, color, text = "NEUTRAL", "warning", "ตลาดกำลังเลือกข้าง แนะนำแบ่งไม้ลงทุนเบาๆ"
        
    market_leaders = []
    leaders = {
        "AAPL": "Apple - ผู้นำโทรศัพท์ iPhone และอุปกรณ์ไอทีระดับโลก",
        "MSFT": "Microsoft - เจ้าของระบบ Windows และคลาวด์องค์กรขนาดใหญ่",
        "GOOGL": "Google - ผู้นำระบบค้นหาข้อมูล อินเทอร์เน็ต และระบบ AI",
        "AMZN": "Amazon - ยักษ์ใหญ่ E-commerce และระบบหลังบ้านคลาวด์อันดับหนึ่ง",
        "TSLA": "Tesla - รถยนต์ไฟฟ้าและเทคโนโลยีพลังงานสะอาดอันดับหนึ่ง"
    }
    for t, desc in leaders.items():
        try:
            tick = yf.Ticker(t).history(period="2d")
            price = round(tick['Close'].iloc[-1], 2)
            chg = round(((tick['Close'].iloc[-1] - tick['Close'].iloc[-2]) / tick['Close'].iloc[-2]) * 100, 2)
            market_leaders.append({"ticker": t, "price": price, "change": chg, "desc": desc})
        except: pass

    safe_havens = []
    havens = {
        "GC=F": "ทองคำ - สินทรัพย์ปลอดภัยสูงสุดในยามที่ตลาดหุ้นเกิดความผันผวน",
        "BTC-USD": "บิตคอยน์ - ดิจิทัลทองคำ สินทรัพย์ทางเลือกที่มีการเติบโตสูง"
    }
    for t, desc in havens.items():
        try:
            tick = yf.Ticker(t).history(period="2d")
            price = round(tick['Close'].iloc[-1], 2)
            chg = round(((tick['Close'].iloc[-1] - tick['Close'].iloc[-2]) / tick['Close'].iloc[-2]) * 100, 2)
            safe_havens.append({"ticker": "GOLD" if t=="GC=F" else "BTC", "price": price, "change": chg, "desc": desc})
        except: pass

    return render_template('index.html', score=score, signal=signal, color=color, text=text, leaders=market_leaders, havens=safe_havens)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('มีชื่อผู้ใช้งานนี้อยู่ในระบบแล้ว!')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == "admin" and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_vip'] = user['is_vip']
            return redirect(url_for('index'))
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/upgrade', methods=['GET', 'POST'])
def upgrade():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files.get('slip')
        if file:
            filename = f"slip_{session['user_id']}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn = get_db_connection()
            conn.execute('UPDATE users SET slip_path = ? WHERE id = ?', (filename, session['user_id']))
            conn.commit()
            conn.close()
            flash('อัปโหลดสลิปเรียบร้อย! กรุณารอแอดมินตรวจสอบสิทธิ์ภายใน 5 นาที')
            return redirect(url_for('index'))
    return render_template('vip.html')

@app.route('/vip-picks')
def vip_picks():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT is_vip FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if not user or user['is_vip'] != 1: return redirect(url_for('upgrade'))
    return render_template('vip_picks.html', stocks=get_vip_stocks())

@app.route('/admin-panel', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('is_admin'): return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST' and 'approve_id' in request.form:
        conn.execute('UPDATE users SET is_vip = 1, slip_path = NULL WHERE id = ?', (request.form['approve_id'],))
        conn.commit()
        flash('อนุมัติสิทธิ์ VIP เรียบร้อยแล้ว!')
    users = conn.execute('SELECT * FROM users WHERE slip_path IS NOT NULL').fetchall()
    conn.close()
    return render_template('admin.html', users=users)
