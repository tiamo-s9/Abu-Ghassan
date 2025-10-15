import sqlite3
import os
import uuid 
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename # استيراد دالة حماية اسم الملف

# ----------------- إعداد Flask وقاعدة البيانات -----------------

app = Flask(__name__) 
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key_here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # الحد الأقصى 16 ميجابايت 

DATABASE_PATH = 'database.db'

# إعداد مجلد رفع الملفات
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        with open('schema.sql', mode='r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Error executing schema: {e}")
    finally:
        conn.close()

if not os.path.exists(DATABASE_PATH):
    init_db()

# ----------------- إعداد Flask-Login -----------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role, request_token):
        self.id = id
        self.username = username
        self.role = role
        self.request_token = request_token

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT id, username, role, request_token FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'], user_data['request_token'])
    return None

# ----------------- مسار الصفحة الرئيسية -----------------

@app.route('/')
def index():
    return render_template('index.html')

# ----------------- مسار مخصص لعرض الملفات المرفوعة -----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """مسار مخصص لعرض الملفات المرفوعة."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ----------------- مسارات المستخدمين -----------------

@app.route('/login', methods=('GET', 'POST'))
def login():
    if current_user.is_authenticated:
        return redirect(url_for('employee_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'], user_data['role'], user_data['request_token'])
            login_user(user)
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('employee_dashboard'))
        else:
            flash('فشل تسجيل الدخول. تحقق من اسم المستخدم وكلمة المرور.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=('GET', 'POST'))
def register():
    conn = get_db_connection()
    user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()

    if user_count > 0:
        flash('لا يمكن إنشاء حسابات جديدة إلا بواسطة المدير عبر لوحة التحكم.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('يجب إدخال اسم المستخدم وكلمة المرور', 'danger')
        else:
            password_hash = generate_password_hash(password)
            request_token = str(uuid.uuid4())
            conn = get_db_connection()
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, request_token) VALUES (?, ?, 'admin', ?)",
                    (username, password_hash, request_token)
                )
                conn.commit()
                flash('تم إنشاء حساب المدير بنجاح. يمكنك الآن تسجيل الدخول.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('اسم المستخدم موجود بالفعل. اختر اسماً آخر.', 'danger')
            finally:
                conn.close()

    return render_template('register.html')

@app.route('/admin/users', methods=('GET', 'POST'))
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('ليس لديك صلاحية المدير للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('employee_dashboard'))

    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', 'employee')
            
            if username and password:
                password_hash = generate_password_hash(password)
                request_token = str(uuid.uuid4())
                try:
                    conn.execute("INSERT INTO users (username, password_hash, role, request_token) VALUES (?, ?, ?, ?)", 
                                 (username, password_hash, role, request_token))
                    conn.commit()
                    flash(f'تمت إضافة المستخدم {username} بنجاح كـ {role}.', 'success')
                except sqlite3.IntegrityError:
                    flash('اسم المستخدم أو الرمز الفريد موجود بالفعل.', 'danger')
        
        elif action == 'delete':
            user_id = request.form.get('user_id')
            if str(user_id) != str(current_user.id):
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                flash('تم حذف المستخدم بنجاح.', 'info')
            else:
                flash('لا يمكنك حذف حسابك الحالي.', 'danger')

    users = conn.execute('SELECT id, username, role, request_token FROM users').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

# ----------------- مسارات الطلبات (العملاء والوكلاء) -----------------

@app.route('/request/<token>', methods=('GET', 'POST'))
def upload_order_by_agent(token):
    """مسار طلب العميل الفريد المرتبط بالوكيل (المكتب) ومعالجة رفع الملفات."""
    conn = get_db_connection()
    agent = conn.execute('SELECT username FROM users WHERE request_token = ?', (token,)).fetchone()
    conn.close()

    if not agent:
        flash('عفواً، رابط الطلب غير صالح.', 'danger')
        return redirect(url_for('index'))
    
    agent_username = agent['username']

    if request.method == 'POST':
        # الحصول على حقول النموذج
        product_type = request.form.get('product_type')
        customer_name = request.form.get('customer_name')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        details = request.form.get('details')
        
        # ----------------- معالجة رفع الملف -----------------
        file = request.files.get('order_file')
        db_filename = "No File" 

        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            db_filename = filename
        # -----------------------------------------------------

        if not all([product_type, customer_name, phone_number, location]):
            flash('الرجاء تعبئة جميع الحقول المطلوبة.', 'danger')
            return render_template('upload.html', agent_token=token)

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO orders (product_type, customer_name, phone_number, location, details, agent_username, file_name) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (product_type, customer_name, phone_number, location, details, agent_username, db_filename)
        )
        conn.commit()
        conn.close()
        flash(f'تم استلام طلبك بنجاح وسيتم معالجته بواسطة الوكيل {agent_username}!', 'success')
        return redirect(url_for('success'))

    return render_template('upload.html', agent_token=token)


@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/dashboard', methods=('GET', 'POST'))
@login_required
def employee_dashboard():
    if current_user.role not in ['admin', 'employee']:
        flash('ليس لديك الصلاحية الكافية للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('new_status')
        
        conn.execute(
            'UPDATE orders SET order_status = ? WHERE id = ?',
            (new_status, order_id)
        )
        conn.commit()
        flash(f'تم تحديث حالة الطلب رقم {order_id} إلى {new_status}', 'success')

    # ----------------- منطق عرض الطلبات حسب الدور (المدير يرى الكل) -----------------
    if current_user.role == 'admin':
        orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    else:
        orders = conn.execute(
            'SELECT * FROM orders WHERE agent_username = ? ORDER BY created_at DESC', 
            (current_user.username,)
        ).fetchall()
        
    conn.close()

    agent_link = url_for('upload_order_by_agent', token=current_user.request_token, _external=True)

    return render_template('dashboard.html', orders=orders, agent_link=agent_link)

if __name__ == '__main__':
    app.run(debug=True)