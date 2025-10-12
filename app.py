import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ----------------- إعداد Flask وقاعدة البيانات -----------------

app = Flask(__name__)
# مفتاح سري ضروري للجلسات (تم حل مشكلة RuntimeError)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key_here')
# لزيادة الحد الأقصى لحجم الطلب (حل مشكلة Bad Request)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 ميجابايت 

DATABASE_PATH = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# دالة تهيئة قاعدة البيانات (تم حل مشكلة الترميز)
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

# تهيئة قاعدة البيانات عند بدء التطبيق إذا لم تكن موجودة
if not os.path.exists(DATABASE_PATH):
    init_db()

# ----------------- إعداد Flask-Login -----------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'])
    return None

# ----------------- مسارات المستخدمين (تسجيل الدخول/الخروج/الإدارة) -----------------

@app.route('/login', methods=('GET', 'POST'))
def login():
    if current_user.is_authenticated:
        return redirect(url_for('employee_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username') # استخدام .get() لتجنب BadRequestKeyError
        password = request.form.get('password')

        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'], user_data['role'])
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

# مسار التسجيل الأولي (محمي: مخصص لإنشاء أول حساب مدير فقط)
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
            conn = get_db_connection()
            try:
                # إنشاء أول مستخدم بدور "admin" بشكل افتراضي
                conn.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
                    (username, password_hash)
                )
                conn.commit()
                flash('تم إنشاء حساب المدير بنجاح. يمكنك الآن تسجيل الدخول.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('اسم المستخدم موجود بالفعل. اختر اسماً آخر.', 'danger')
            finally:
                conn.close()

    return render_template('register.html')

# ----------------- مسار لوحة المدير لإدارة المستخدمين -----------------

@app.route('/admin/users', methods=('GET', 'POST'))
@login_required
def admin_users():
    # حماية: لا يمكن الوصول إلا للمديرين
    if current_user.role != 'admin':
        flash('ليس لديك صلاحية المدير للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('employee_dashboard'))

    conn = get_db_connection()

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role')
            if username and password:
                password_hash = generate_password_hash(password)
                try:
                    conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, password_hash, role))
                    conn.commit()
                    flash(f'تمت إضافة المستخدم {username} بنجاح كـ {role}.', 'success')
                except sqlite3.IntegrityError:
                    flash('اسم المستخدم موجود بالفعل.', 'danger')
        
        elif action == 'delete':
            user_id = request.form.get('user_id')
            if str(user_id) != str(current_user.id):
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                flash('تم حذف المستخدم بنجاح.', 'info')
            else:
                flash('لا يمكنك حذف حسابك الحالي.', 'danger')

    users = conn.execute('SELECT id, username, role FROM users').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

# ----------------- مسارات الطلبات (العملاء والموظفين) -----------------

@app.route('/', methods=('GET', 'POST'))
@app.route('/upload', methods=('GET', 'POST'))
def upload_order():
    if request.method == 'POST':
        # استخدام .get() لتجنب BadRequestKeyError
        product_type = request.form.get('product_type')
        customer_name = request.form.get('customer_name')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        details = request.form.get('details')

        if not all([product_type, customer_name, phone_number, location]):
            flash('الرجاء تعبئة جميع الحقول المطلوبة.', 'danger')
            return render_template('upload.html')

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO orders (product_type, customer_name, phone_number, location, details) VALUES (?, ?, ?, ?, ?)',
            (product_type, customer_name, phone_number, location, details)
        )
        conn.commit()
        conn.close()
        flash('تم استلام طلبك بنجاح!', 'success')
        return redirect(url_for('success'))

    return render_template('upload.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/dashboard', methods=('GET', 'POST'))
@login_required
def employee_dashboard():
    # حماية لوحة القيادة بنظام الأدوار
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

    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('dashboard.html', orders=orders)

if __name__ == '__main__':
    app.run(debug=True)