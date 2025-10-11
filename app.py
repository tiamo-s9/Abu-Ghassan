import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ----------------- إعداد Flask وقاعدة البيانات -----------------

app = Flask(__name__)
# مفتاح سري ضروري لجلسات Flask و Flask-Login
# يجب تغيير القيمة الافتراضية 'your_strong_secret_key_here' عند النشر
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key_here')

# تحديد مسار قاعدة البيانات
DATABASE_PATH = 'database.db'

# دالة للاتصال بقاعدة البيانات
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# دالة لتهيئة قاعدة البيانات (إنشاء الجداول)
def init_db():
    conn = get_db_connection()
    try:
        # **التصحيح الحاسم لمشكلة الترميز (UnicodeDecodeError):**
        # نحدد الترميز (encoding) بوضوح ليكون 'utf-8'
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
login_manager.login_view = 'login' # تحديد الصفحة التي يتم توجيه المستخدم إليها لتسجيل الدخول

# نموذج المستخدم لـ Flask-Login
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

# دالة لتحميل المستخدم من الجلسة
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT id, username, role FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'])
    return None

# ----------------- مسارات المستخدمين (تسجيل الدخول/الخروج) -----------------

# مسار تسجيل الدخول
@app.route('/login', methods=('GET', 'POST'))
def login():
    if current_user.is_authenticated:
        return redirect(url_for('employee_dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'], user_data['role'])
            login_user(user)
            flash('تم تسجيل الدخول بنجاح!', 'success')
            # توجيه المستخدم إلى لوحة القيادة بعد نجاح تسجيل الدخول
            return redirect(url_for('employee_dashboard'))
        else:
            flash('فشل تسجيل الدخول. تحقق من اسم المستخدم وكلمة المرور.', 'danger')

    return render_template('login.html')

# مسار تسجيل الخروج
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح.', 'info')
    return redirect(url_for('login'))

# مسار التسجيل (لإنشاء أول موظف/مدير فقط) - يجب حذف هذا المسار لاحقاً
@app.route('/register', methods=('GET', 'POST'))
def register():
    # يمكن إضافة شرط للحماية هنا، مثل السماح بالتسجيل فقط إذا لم يكن هناك أي مستخدمين
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('يجب إدخال اسم المستخدم وكلمة المرور', 'danger')
        else:
            password_hash = generate_password_hash(password)
            conn = get_db_connection()
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash)
                )
                conn.commit()
                flash('تم إنشاء الحساب بنجاح. يمكنك الآن تسجيل الدخول.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('اسم المستخدم موجود بالفعل. اختر اسماً آخر.', 'danger')
            finally:
                conn.close()

    return render_template('register.html')


# ----------------- مسارات الطلبات (العملاء والموظفين) -----------------

# مسار العميل (رفع الطلب)
@app.route('/', methods=('GET', 'POST'))
@app.route('/upload', methods=('GET', 'POST'))
def upload_order():
    if request.method == 'POST':
        product_type = request.form['product_type']
        customer_name = request.form['customer_name']
        phone_number = request.form['phone_number']
        location = request.form['location']
        details = request.form['details']

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

# صفحة النجاح بعد رفع الطلب
@app.route('/success')
def success():
    return render_template('success.html')

# مسار لوحة الموظف (تمت حمايته بـ @login_required)
@app.route('/dashboard', methods=('GET', 'POST'))
@login_required # لا يمكن الوصول إلا بعد تسجيل الدخول
def employee_dashboard():
    conn = get_db_connection()

    if request.method == 'POST':
        order_id = request.form['order_id']
        new_status = request.form['new_status']
        conn.execute(
            'UPDATE orders SET order_status = ? WHERE id = ?',
            (new_status, order_id)
        )
        conn.commit()
        flash(f'تم تحديث حالة الطلب رقم {order_id} إلى {new_status}', 'success')

    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('dashboard.html', orders=orders)

# تشغيل التطبيق
if __name__ == '__main__':
    app.run(debug=True)