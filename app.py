import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

# 1. إعدادات المشروع الأساسية
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# التأكد من وجود مجلد الحفظ
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 2. إعداد قاعدة البيانات (SQLite)
DATABASE = 'database.db'

# *** وظيفة فتح اتصال جديد في كل مرة ***
def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    # دالة لإنشاء الجدول Orders عند تشغيل التطبيق لأول مرة
    with app.app_context():
        db = get_db()
        try:
            with app.open_resource('schema.sql', mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()
        except sqlite3.OperationalError as e:
            print(f"Database Initialization Warning: {e}")
        finally:
            db.close() # إغلاق الاتصال بعد التهيئة

# 3. مسار رفع الطلبات (واجهة العميل)
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'

        if file:
            client_name = request.form['client_name']
            client_phone = request.form['client_phone']
            service_type = request.form['service_type']
            
            # توليد اسم ملف فريد وتخزينه
            filename = f"{client_name}_{os.path.basename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            db = None
            order_id = None
            try:
                # حفظ الطلب في قاعدة البيانات
                db = get_db()
                db.execute(
                    'INSERT INTO Orders (client_name, client_phone, file_name, file_path, service_type, order_status) VALUES (?, ?, ?, ?, ?, ?)',
                    (client_name, client_phone, filename, file_path, service_type, 'New')
                )
                db.commit()
                order_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            except Exception as e:
                print(f"DATABASE INSERT ERROR: {e}")
                return "حدث خطأ في حفظ الطلب، الرجاء المحاولة لاحقاً."
            finally:
                if db:
                    db.close() # إغلاق الاتصال بعد الانتهاء
            
            # *** التعديل هنا: التوجيه لصفحة النجاح الجديدة ***
            return render_template('success.html', order_id=order_id)
            
    return render_template('upload.html')

# 4. مسار لوحة تحكم الطلبات (واجهة الموظف)
@app.route('/dashboard')
def dashboard():
    orders = []
    db = None
    try:
        db = get_db()
        orders = db.execute(
            'SELECT * FROM Orders ORDER BY '
            'CASE order_status '
            'WHEN "New" THEN 1 '
            'WHEN "In Progress" THEN 2 '
            'WHEN "Ready" THEN 3 '
            'ELSE 4 END, created_at DESC'
        ).fetchall()
    except Exception as e:
        print(f"DATABASE RETRIEVAL ERROR: {e}") 
    finally:
        if db:
            db.close()
        
    return render_template('dashboard.html', orders=orders)

# 5. مسار لتغيير حالة الطلب
@app.route('/change_status/<int:order_id>', methods=['POST'])
def change_status(order_id):
    new_status = request.form.get('new_status')
    if new_status in ['In Progress', 'Ready']:
        db = None
        try:
            db = get_db()
            db.execute(
                'UPDATE Orders SET order_status = ? WHERE order_id = ?',
                (new_status, order_id)
            )
            db.commit()
        except Exception as e:
            print(f"ERROR UPDATING STATUS: {e}")
        finally:
            if db:
                db.close()
                
    return redirect(url_for('dashboard'))

# 6. مسار عرض الملفات المرفوعة للموظف
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    # حلول الاستقرار
    app.run(host='0.0.0.0', debug=False, threaded=False)