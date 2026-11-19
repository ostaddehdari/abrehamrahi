# اتصال سایت به API

توکن دامنه و کلید امضا را در صفحهٔ مدیریت بسازید. این دو مقدار باید فقط در متغیرهای محیطی بک‌اند سایت قرار گیرند و نباید در JavaScript عمومی منتشر شوند.

## قرارداد امضا

بدنهٔ خام درخواست را SHA-256 کنید و متن زیر را با کلید `signing_secret` و HMAC-SHA256 امضا کنید:

```text
timestamp
METHOD
/abrehamrahi/v1/path
sha256(raw_body)
```

هدرها:

```text
X-ABR-Client-Token: abrc_...
X-ABR-Domain: example.com
X-ABR-Timestamp: 1795090000
X-ABR-Content-SHA256: sha256(raw_body)
X-ABR-Signature: hexadecimal-hmac
Authorization: Bearer abrs_...   # بعد از ورود کاربر
```

اختلاف زمان مجاز پنج دقیقه است.

## نمونه Python

```python
import hashlib, hmac, json, os, time
import httpx

BASE = "https://srun.ir"
PATH = "/abrehamrahi/v1/auth/sms/request"
body = json.dumps({"phone": "09123456789"}, separators=(",", ":")).encode()
timestamp = str(int(time.time()))
body_hash = hashlib.sha256(body).hexdigest()
message = f"{timestamp}\nPOST\n{PATH}\n{body_hash}".encode()
signature = hmac.new(os.environ["ABR_SIGNING_SECRET"].encode(), message, hashlib.sha256).hexdigest()

response = httpx.post(BASE + PATH, content=body, headers={
    "Content-Type": "application/json",
    "X-ABR-Client-Token": os.environ["ABR_CLIENT_TOKEN"],
    "X-ABR-Domain": "example.com",
    "X-ABR-Timestamp": timestamp,
    "X-ABR-Content-SHA256": body_hash,
    "X-ABR-Signature": signature,
})
response.raise_for_status()
print(response.json())
```

## نمونه PHP

```php
<?php
$path = '/abrehamrahi/v1/auth/sms/request';
$body = json_encode(['phone' => '09123456789'], JSON_UNESCAPED_SLASHES);
$timestamp = (string) time();
$message = $timestamp."\nPOST\n".$path."\n".hash('sha256', $body);
$signature = hash_hmac('sha256', $message, getenv('ABR_SIGNING_SECRET'));
$ch = curl_init('https://srun.ir'.$path);
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => $body,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => [
        'Content-Type: application/json',
        'X-ABR-Client-Token: '.getenv('ABR_CLIENT_TOKEN'),
        'X-ABR-Domain: example.com',
        'X-ABR-Timestamp: '.$timestamp,
        'X-ABR-Content-SHA256: '.hash('sha256', $body),
        'X-ABR-Signature: '.$signature,
    ],
]);
$result = curl_exec($ch);
?>
```

برای `multipart/form-data` باید دقیقاً همان بایت‌هایی را امضا کنید که ارسال می‌شوند. ساده‌ترین روش در PHP این است که بارگذاری را از بک‌اند خودتان به این درگاه انجام دهید و امضای بدنه را پس از ساخت بدنهٔ multipart محاسبه کنید. مشخصات و نمونه‌های قابل اجرا در `/docs` نیز در دسترس‌اند.

## مسیرهای مدیریت فایل افزوده‌شده

| روش | مسیر | کاربرد |
|---|---|---|
| `GET` | `/abrehamrahi/v1/files?recursive=true` | فهرست درختی؛ برای هر فایل `cdn_url` پایدار می‌سازد |
| `GET` | `/abrehamrahi/v1/quota` | کل، مصرف‌شده و باقی‌ماندهٔ فضای حساب |
| `DELETE` | `/abrehamrahi/v1/files/{id}` | انتقال فایل یا پوشه به زباله‌دان |
| `DELETE` | `/abrehamrahi/v1/files/{id}?permanent=true` | حذف دائمی و غیرقابل‌بازگشت |

صفحهٔ `/abrehamrahi/testpage` همین گردش را برای چند حساب به‌صورت تصویری آزمایش می‌کند و با نام کاربری و رمز مدیریت سامانه محافظت می‌شود.

