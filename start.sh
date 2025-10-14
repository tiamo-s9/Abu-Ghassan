#!/usr/bin/env bash

# تهيئة قاعدة البيانات (حل مشكلة Bad Gateway)
python app.py & PID=$!
sleep 5 

# قتل عملية التشغيل المؤقتة
kill $PID

# تشغيل خادم Gunicorn
gunicorn app:app