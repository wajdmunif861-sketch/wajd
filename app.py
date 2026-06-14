from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'wajd_secret_key_for_sessions'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# الصيغ المسموحة للصور والفيديوهات
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # جدول العقارات (أضفنا عمود video_path)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            type TEXT NOT NULL,
            price INTEGER NOT NULL,
            location_url TEXT,
            notes TEXT,
            category TEXT,
            status TEXT DEFAULT 'متاح',
            video_path TEXT
        )
    ''')
    # جدول الصور
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS property_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            image_path TEXT,
            FOREIGN KEY(property_id) REFERENCES properties(id)
        )
    ''')
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username').strip()
    password = request.form.get('password').strip()
    
    if username == 'wajd' and password == 'admin123':
        session['user'] = 'wajd'
        return redirect(url_for('admin_home'))
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    if user:
        if user[2] == password:
            session['user'] = username
            conn.close()
            return redirect(url_for('marketer_home'))
        else:
            conn.close()
            return "<h3>كلمة المرور خاطئة لهذا المسوق!</h3>"
    else:
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            session['user'] = username
            conn.close()
            return redirect(url_for('marketer_home'))
        except:
            conn.close()
            return "<h3>حدث خطأ أثناء التسجيل، يرجى المحاولة مجدداً.</h3>"

@app.route('/admin-dashboard', methods=['GET', 'POST'])
def admin_home():
    if session.get('user') != 'wajd':
        return redirect(url_for('index'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        region = request.form.get('region')
        prop_type = request.form.get('type')
        price = request.form.get('price')
        location_url = request.form.get('location_url')
        notes = request.form.get('notes')
        category = request.form.get('category')
        
        # معالجة رفع الفيديو (إن وجد)
        video_file = request.files.get('video')
        video_filename = None
        if video_file and video_file.filename != '':
            ext = video_file.filename.split('.')[-1].lower()
            if ext in ALLOWED_VIDEO_EXTENSIONS:
                secured_vid = secure_filename(video_file.filename)
                video_filename = f"vid_{id}_{secured_vid}"
                # سيتم تحديث الاسم الفريد بعد جلب رقم العقار
        
        cursor.execute('''
            INSERT INTO properties (region, type, price, location_url, notes, category, video_path) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (region, prop_type, price, location_url, notes, category, video_filename))
        property_id = cursor.lastrowid
        
        # إذا كان هناك فيديو، نقوم بحفظه باسم يحتوي على ID العقار لضمان عدم التكرار
        if video_file and video_file.filename != '':
            ext = video_file.filename.split('.')[-1].lower()
            if ext in ALLOWED_VIDEO_EXTENSIONS:
                video_filename = f"vid_{property_id}.{ext}"
                video_file.save(os.path.join(app.config['UPLOAD_FOLDER'], video_filename))
                cursor.execute('UPDATE properties SET video_path = ? WHERE id = ?', (video_filename, property_id))
        
        # معالجة رفع الصور المتعددة
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                unique_filename = f"{property_id}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                cursor.execute('INSERT INTO property_images (property_id, image_path) VALUES (?, ?)', 
                               (property_id, unique_filename))
        conn.commit()
        return redirect(url_for('admin_home'))

    cursor.execute('SELECT * FROM properties')
    properties = cursor.fetchall()
    
    cursor.execute('SELECT username, password FROM users')
    marketers = cursor.fetchall()
    
    conn.close()
    return render_template('index.html', properties=properties, marketers=marketers)

@app.route('/toggle-status/<int:prop_id>')
def toggle_status(prop_id):
    if session.get('user') != 'wajd':
        return redirect(url_for('index'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM properties WHERE id = ?', (prop_id,))
    current_status = cursor.fetchone()[0]
    new_status = 'مؤجر' if current_status == 'متاح' else 'متاح'
    cursor.execute('UPDATE properties SET status = ? WHERE id = ?', (new_status, prop_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_home'))

@app.route('/marketer-dashboard')
def marketer_home():
    if not session.get('user') or session.get('user') == 'wajd':
        return redirect(url_for('index'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM properties WHERE status = 'متاح'")
    rows = cursor.fetchall()
    
    available_properties = []
    for row in rows:
        prop = dict(row)
        cursor.execute("SELECT image_path FROM property_images WHERE property_id = ?", (prop['id'],))
        images = [img['image_path'] for img in cursor.fetchall()]
        prop['images'] = images
        available_properties.append(prop)
        
    conn.close()
    return render_template('marketer.html', properties=available_properties)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
