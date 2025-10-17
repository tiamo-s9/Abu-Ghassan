import sqlite3
import os
import uuid 
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import re # للاستخدام في التحقق من صحة البريد الإلكتروني (اختياري)

# ----------------- إعداد Flask وقاعدة البيانات -----------------

app = Flask(__name__) 
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_strong_secret_key_here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

DATABASE_PATH = 'database.db'
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
        
        # 🚨 إنشاء حساب مدير افتراضي إذا كانت القاعدة فارغة 🚨
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            initial_username = 'admin'
            initial_password_hash = generate_password_hash('123456') # غير هذا!
            initial_token = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (username, password_hash, role, request_token, first_name, last_name, email) VALUES (?, ?, 'admin', ?, ?, ?, ?)",
                (initial_username, initial_password_hash, initial_token, 'مدير', 'النظام', 'admin@example.com')
            )
            conn.commit()
            print("Default admin account created.")

    except sqlite3.Error as e:
        print(f"Error executing schema: {e}")
    finally:
        conn.close()

if not os.path.exists(DATABASE_PATH) or os.path.getsize(DATABASE_PATH) == 0:
    init_db()

# ----------------- إعداد Flask-Login -----------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.remember_cookie_duration = 30 * 24 * 60 * 60 # تذكرني لمدة 30 يوم

class User(UserMixin):
    def __init__(self, id, username, role, request_token, first_name=None, last_name=None):
        self.id = id
        self.username = username
        self.role = role
        self.request_token = request_token
        self.first_name = first_name
        self.last_name = last_name

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT id, username, role, request_token, first_name, last_name FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'], user_data['request_token'], user_data['first_name'], user_data['last_name'])
    return None

# ----------------- مسار الصفحة الرئيسية وعرض الملفات -----------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """مسار مخصص لعرض الملفات المرفوعة."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ----------------- مسارات المستخدمين (تسجيل دخول وتسجيل) -----------------

@app.route('/login', methods=('GET', 'POST'))
def login():
    # ... (منطق تسجيل الدخول القديم مع إضافة 'remember' me) ...
    if current_user.is_authenticated:
        return redirect(url_for('employee_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') # جديد

        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'], user_data['role'], user_data['request_token'])
            # 💡 تمرير قيمة remember إلى login_user
            login_user(user, remember=bool(remember)) 
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
    if request.method == 'POST':
        # 💡 جمع جميع الحقول الجديدة
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        work_type = request.form.get('work_type')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        gender = request.form.get('gender')
        age = request.form.get('age')
        
        # 💡 حقل التحقق من الروبوت (CAPTCHA بسيط)
        captcha_response = request.form.get('captcha')
        
        required_fields = [username, password, first_name, last_name, email, phone_number, gender, age, work_type]

        if not all(required_fields):
            flash('الرجاء تعبئة جميع الحقول المطلوبة.', 'danger')
            return render_template('register.html')
            
        if password and len(password) < 6:
            flash('يجب أن تكون كلمة المرور 6 أحرف على الأقل.', 'danger')
            return render_template('register.html')

        # 🚨 التحقق من الكابتشا البسيط
        if captcha_response != '4': # افترض أن سؤال CAPTCHA هو (2 + 2 = ?)
             flash('الرجاء حل سؤال التحقق بشكل صحيح.', 'danger')
             return render_template('register.html')

        password_hash = generate_password_hash(password)
        request_token = str(uuid.uuid4()) # رمز فريد لكل وكيل
        
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO users (username, password_hash, role, request_token, first_name, last_name, work_type, email, phone_number, gender, age) 
                VALUES (?, ?, 'employee', ?, ?, ?, ?, ?, ?, ?, ?)""", # 🚨 الدور الافتراضي هو 'employee'
                (username, password_hash, request_token, first_name, last_name, work_type, email, phone_number, gender, int(age))
            )
            conn.commit()
            flash('تم إنشاء حسابك بنجاح. يمكنك الآن تسجيل الدخول.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('اسم المستخدم أو البريد الإلكتروني موجود بالفعل. اختر بيانات أخرى.', 'danger')
        except ValueError:
            flash('الرجاء إدخال العمر كرقم صحيح.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

# ----------------- مسارات المدير -----------------

@app.route('/admin/users', methods=('GET', 'POST'))
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('ليس لديك صلاحية المدير للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('employee_dashboard'))

    conn = get_db_connection()
    # ... (منطق إضافة وحذف المستخدمين القديم - لا نحتاج الإضافة هنا بعد الآن لكن سنبقيها) ...
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role', 'employee')
            
            # 💡 نحتاج الحقول الجديدة هنا أيضًا إذا كنا نريد الإضافة من المدير
            first_name = request.form.get('first_name', 'N/A')
            last_name = request.form.get('last_name', 'N/A')
            email = request.form.get('email', 'N/A')
            work_type = request.form.get('work_type', 'N/A')
            
            if username and password:
                password_hash = generate_password_hash(password)
                request_token = str(uuid.uuid4())
                try:
                    conn.execute("""INSERT INTO users (username, password_hash, role, request_token, first_name, last_name, work_type, email) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                                 (username, password_hash, role, request_token, first_name, last_name, work_type, email))
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

    users = conn.execute('SELECT id, username, role, request_token, first_name, last_name, email, phone_number, work_type FROM users').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

# ----------------- مسارات الطلبات (العملاء والوكلاء) -----------------

@app.route('/request/<token>', methods=('GET', 'POST'))
def upload_order_by_agent(token):
    """مسار طلب العميل الفريد ومعالجة رفع الملفات وإعادة التحميل الذاتي (Self-Reload) بعد النجاح."""
    conn = get_db_connection()
    agent = conn.execute('SELECT username, first_name FROM users WHERE request_token = ?', (token,)).fetchone()
    conn.close()

    if not agent:
        flash('عفواً، رابط الطلب غير صالح.', 'danger')
        return redirect(url_for('index'))
    
    agent_username = agent['username']
    agent_name = agent['first_name'] # اسم الوكيل للعرض في رسالة النجاح

    if request.method == 'POST':
        product_type = request.form.get('product_type')
        customer_name = request.form.get('customer_name')
        phone_number = request.form.get('phone_number')
        location = request.form.get('location')
        details = request.form.get('details')
        
        file = request.files.get('order_file')
        db_filename = "No File" 

        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            db_filename = filename

        if not all([product_type, customer_name, phone_number, location]):
            flash('الرجاء تعبئة جميع الحقول المطلوبة.', 'danger')
            return render_template('upload.html', agent_token=token, agent_name=agent_name)

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO orders (product_type, customer_name, phone_number, location, details, agent_username, file_name) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (product_type, customer_name, phone_number, location, details, agent_username, db_filename)
        )
        conn.commit()
        conn.close()
        
        flash(f'تم استلام طلبك بنجاح وسيتم معالجته بواسطة الوكيل {agent_name}!', 'success')
        
        # 💡 التعديل هنا: إعادة التوجيه إلى نفس صفحة الطلب الفريدة لإرسال طلب آخر
        return redirect(url_for('upload_order_by_agent', token=token)) 

    # عند التحميل الأول للصفحة
    return render_template('upload.html', agent_token=token, agent_name=agent_name)


@app.route('/dashboard', methods=('GET', 'POST'))
@login_required
def employee_dashboard():
    # ... (منطق لوحة التحكم القديم) ...
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

    # منطق عرض الطلبات حسب الدور (المدير يرى الكل)
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
    # 💡 تأكد من أنك تستخدم هذا فقط محليًا.
    # عند النشر على Render، يجب أن تعتمد على gunicorn
    app.run(debug=True)