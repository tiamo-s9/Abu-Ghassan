-- جدول المستخدمين لتسجيل الدخول
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee'
);

-- الجدول الحالي لطلبات العملاء
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_type TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    location TEXT NOT NULL,
    details TEXT,
    order_status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ملاحظة: للتطبيق المحلي، يجب حذف ملف database.db لإعادة إنشاء الجداول