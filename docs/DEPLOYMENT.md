# استقرار روی سرور

## نصب نخستین بار

```bash
ssh -p 2233 root@5.61.27.185
git clone https://github.com/ostaddehdari/abrehamrahi.git /opt/abrehamrahi
bash /opt/abrehamrahi/deploy/install.sh
```

اسکریپت بسته‌های لازم را نصب، virtualenv را ایجاد، فایل محیطی را تولید، سرویس systemd را فعال و location مربوط به `/abrehamrahi` را داخل server block دامنهٔ `srun.ir` اضافه می‌کند. قبل از ویرایش Nginx یک فایل پشتیبان کنار فایل اصلی می‌سازد و قبل از reload دستور `nginx -t` اجرا می‌شود.

اگر فایل تنظیمات دامنه خودکار پیدا نشد:

```bash
NGINX_SITE_CONFIG=/etc/nginx/sites-available/srun.ir \
  bash /opt/abrehamrahi/deploy/install.sh
```

رمز مدیر تولیدشده در `/etc/abrehamrahi.env` قرار می‌گیرد. آن را فقط با دسترسی root بخوانید:

```bash
grep '^ADMIN_' /etc/abrehamrahi.env
```

سپس صفحهٔ `https://srun.ir/abrehamrahi/admin/tokens` را باز کنید.

## به‌روزرسانی

```bash
ssh -p 2233 root@5.61.27.185
bash /opt/abrehamrahi/deploy/update.sh
```

## بررسی سرویس

```bash
systemctl status abrehamrahi-api --no-pager
journalctl -u abrehamrahi-api -n 100 --no-pager
nginx -t
curl -i http://127.0.0.1:18765/health
curl -i https://srun.ir/abrehamrahi/health
```

## فایل‌های عملیاتی

| مورد | مسیر |
|---|---|
| کد | `/opt/abrehamrahi` |
| محیط و رمزها | `/etc/abrehamrahi.env` |
| SQLite | `/var/lib/abrehamrahi/abrehamrahi.sqlite3` |
| سرویس | `/etc/systemd/system/abrehamrahi-api.service` |
| قطعه Nginx | `/etc/nginx/snippets/abrehamrahi.conf` |

از سه مورد محیط، پایگاه‌داده و فایل پیکربندی Nginx پشتیبان بگیرید. `ENCRYPTION_KEY` باید همراه SQLite نگهداری شود؛ بدون آن توکن‌های رمزگذاری‌شده قابل استفاده نیستند.

## انتقال دستی بدون Git

روش اصلی Git است. در صورت نیاز می‌توان پروژه را با `rsync` انتقال داد:

```bash
rsync -avz -e 'ssh -p 2233' --exclude='.venv' --exclude='.env' \
  ./abrehamrahi/ root@5.61.27.185:/opt/abrehamrahi/
ssh -p 2233 root@5.61.27.185 'bash /opt/abrehamrahi/deploy/install.sh'
```

