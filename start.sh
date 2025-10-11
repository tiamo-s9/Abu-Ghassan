#!/usr/bin/env bash

# الأمر الأول: تهيئة قاعدة البيانات قبل التشغيل
# يضمن هذا الأمر إنشاء ملف database.db عند أول تشغيل على Render
python -c "from app import init_db; init_db()"

# الأمر الثاني: تشغيل خادم Gunicorn لتشغيل التطبيق
gunicorn app:app