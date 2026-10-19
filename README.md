# EasyWarehouse

برنامه دسکتاپ **مدیریت انبار** برای ویندوز — ساده، سبک، بدون نیاز به نصب پایتون روی سیستم کاربر.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-1.0.0-teal)

## امکانات

- کتابخانه کالا با **کد خودکار** (`P001`, `P002`, ...)
- ثبت **ورود / خروج / عودت**
- Combobox با نمایش «کد - نام» و به‌روزرسانی خودکار موجودی و واحد
- هشدار کمبود و موجودی منفی
- تم **فیروزه‌ای آبی آسمان ایران**
- راهنمای کاربر با **F1**
- پشتیبان‌گیری و بازیابی دیتابیس
- دیتابیس در `%APPDATA%\\EasyWarehouse\\anbar.db`

## اجرا برای کاربر نهایی

1. فایل `EasyWarehouse.exe` را از [Releases](https://github.com/Tahmoures54/EasyWarehouse/releases) دانلود کنید.
2. دابل‌کلیک کنید — نیازی به نصب پایتون نیست.

## ساخت از سورس (ویندوز)

```bat
git clone https://github.com/Tahmoures54/EasyWarehouse.git
cd EasyWarehouse
scripts\\build_windows.bat
```

خروجی: `dist\\EasyWarehouse.exe`

## اجرای توسعه

```bash
python -m app.main
```

## تست

```bash
pip install pytest pytest-cov
pytest -v --cov=app --cov-report=term-missing
```

## ساختار

```
EasyWarehouse/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database/
│   ├── models/
│   ├── services/
│   └── ui/
├── assets/
├── scripts/
├── tests/
├── LICENSE
├── CHANGELOG.md
└── VERSION.txt
```

## راهنمای سریع ثبت تراکنش

1. کالا را از Combobox انتخاب کنید.
2. نوع را مشخص کنید (ورود / خروج / عودت).
3. تعداد را وارد کنید.
4. ثبت را بزنید.

## لایسنس

MIT — آزاد برای استفاده و تغییر.
