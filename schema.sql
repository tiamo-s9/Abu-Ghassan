-- جدول المستخدمين (Users)
-- تم إضافة حقول الأمان والتفاصيل الجديدة
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- حقول تسجيل الدخول الأساسية
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee', -- الافتراضي: 'employee'
    request_token TEXT NOT NULL UNIQUE,

    -- حقول الأمان والتفاصيل الجديدة
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    work_type TEXT,
    email TEXT NOT NULL UNIQUE,
    phone_number TEXT,
    gender TEXT,
    age INTEGER,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- جدول الطلبات (Orders)
DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_type TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    location TEXT NOT NULL,
    details TEXT,
    file_name TEXT DEFAULT 'No File',
    order_status TEXT NOT NULL DEFAULT 'Pending',
    agent_username TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);