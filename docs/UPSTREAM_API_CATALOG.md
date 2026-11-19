# کاتالوگ API مشاهده‌شده در APK ابرهمراهی 1.5.14.00

مبنای این جدول تحلیل ایستای `classes.dex` و `classes2.dex` است. «قطعی» یعنی مسیر، روش و مدل مرتبط در زنجیرهٔ ساخت درخواست مشاهده شده؛ «قوی» یعنی مسیر و کلاس فراخوان یا پارامترها دیده شده؛ «نیازمند تست» یعنی مسیر وجود دارد اما قرارداد کامل پاسخ یا درخواست از APK به تنهایی قطعی نیست. این سند فهرست APIهای قابل بازیابی از اپ است و الزاماً همهٔ APIهای داخلی سرور نیست.

Base URL مشاهده‌شده: `https://abrehamrahi.ir` و رشتهٔ `https://abrehamrahi.ir/api/`.

## احراز هویت و حساب

| روش | مسیر | شواهد/کارکرد | اطمینان |
|---|---|---|---|
| GET | `/api/v1/captcha/get-captcha/` | دریافت captcha | قطعی |
| POST | `/api/v6/profile/auth/generate-code/` | `phone`, `captcha_id`, `captcha_value`, `captcha_provider`, `request_type`, `prefix` | قطعی |
| POST | `/api/v6/profile/auth/validate-otp/` | `phone`, `code`, `prefix` | قطعی |
| POST | `/api/v6/profile/auth/login/` | ورود با `phone` و `password` یا `code`؛ پاسخ `access`, `refresh`, `token_id` | قطعی و تست‌شده |
| POST | `/api/v2/profile/auth/token-refresh/` | `refresh`؛ پاسخ access/refresh تازه | قطعی |
| POST | `/api/v2/profile/auth/logout/` | خروج | قوی |
| POST | `/api/v2/profile/auth/change-password/` | `password`, `new_password`, `refresh`, `code` اختیاری | قطعی؛ ترکیب فیلد نیازمند تست |
| POST | `/api/v6/profile/auth/change-phone/` | تغییر شماره | قوی |
| POST | `/api/v3/profile/auth/delete-account/` | حذف حساب | قوی |
| GET | `/api/v1/configuration/get-password-policies/` | سیاست رمز | قطعی |
| GET | `/api/v1/configuration/server-time/` | زمان سرور | قطعی |

## پروفایل، دستگاه و اعلان

| روش | مسیر | کارکرد | اطمینان |
|---|---|---|---|
| GET | `/api/v6/profile/auth/get-profile/` | دریافت پروفایل | قطعی |
| POST | `/api/v6/profile/auth/set-profile/` | ویرایش پروفایل | قطعی |
| POST | `/api/v1/profile/auth/create-profile-url/` | URL پروفایل | قوی |
| GET | `/api/v2/profile/list-active-tokens/` | نشست‌های فعال | قطعی |
| POST | `/api/v2/profile/delete-tokens/` | حذف نشست‌ها | قطعی |
| GET | `/api/v6/profile/contact/list-contact/` | فهرست مخاطبان | قطعی |
| POST | `/api/v6/profile/contact/create-contact/` | ساخت مخاطب | قطعی |
| POST | `/api/v6/profile/contact/delete-contact/` | حذف مخاطب | قطعی |
| POST | `/api/v6/profile/contact/sync-contact/` | همگام‌سازی مخاطب | قطعی |
| POST | `/api/v1/notification/create-firebase-token/` | ثبت توکن اعلان | قطعی |
| POST | `/api/v1/notification/delete-firebase-token/` | حذف توکن اعلان | قطعی |
| GET | `/api/v1/notification/list-notifications/` | فهرست اعلان | قطعی |
| POST | `/api/v1/notification/read-notifications/` | خوانده‌شدن | قطعی |
| POST | `/api/v1/notification/unread-notifications/` | خوانده‌نشده | قطعی |
| POST | `/api/v1/notification/delete-notifications/` | حذف اعلان | قطعی |

## فایل، پوشه و بارگذاری

| روش | مسیر | کارکرد/مدل | اطمینان |
|---|---|---|---|
| GET | `/api/v2/flat/list-objects/` | `parent`, `limit`, `offset`, `recursive`, فیلترها؛ نتایج فایل و پوشه | قطعی و تست‌شده |
| POST | `/api/v2/flat/create-folder/` | `name`, `parent` | قطعی |
| GET | `/api/v2/flat/get-object/{id}/` | جزئیات شیء | قطعی |
| GET | `/api/v1/flat/get-download-url/{id}/` | پاسخ `download_url` | قطعی |
| POST | `/api/v2/flat/start-upload/` | درخواست `obj_size`؛ پاسخ `upload_id`, `key`, `signed_urls`, `chunk_size` | قطعی |
| PUT | signed URL | ارسال هر chunk؛ دریافت `ETag` | قطعی |
| POST | `/api/v2/flat/complete-upload/` | `key`, `name`, `parent`, `upload_id`, `parts`, `force_overwrite`, `version_group`, `is_hidden` | قطعی |
| POST | `/api/v2/flat/abort-upload/` | `upload_id`, `key` | قطعی |
| GET | `/api/v2/flat/get-version-history/` | `version_group` | قوی |
| POST | `/api/v2/rgw/move-object/` | انتقال | قوی |
| POST | `/api/v5/rgw/copy-object/` | کپی | قوی |
| POST | `/api/v2/rgw/rename-object/` | `obj_id`, `name` | قطعی |
| POST | `/api/v2/rgw/trash-objects/` | `obj_ids` | قطعی |
| DELETE | `/api/v3/rgw/delete-object/{id}/` | حذف قطعی | قوی |
| POST | `/api/v5/rgw/restore-object/` | `obj_id` | قطعی |
| POST | `/api/v3/rgw/delete-verion-groups/` | حذف نسخه‌ها؛ املای `verion` در APK | قوی |
| GET | `/api/v3/rgw/get-quota/` | فضای مصرف‌شده/سهمیه | قطعی |
| POST | `/api/v3/rgw/zip-objects/` | ساخت ZIP | قطعی |

## اشتراک، لینک عمومی و علاقه‌مندی

| روش | مسیر | کارکرد | اطمینان |
|---|---|---|---|
| POST | `/api/v2/sharing/public-link/create/` | لینک عمومی | قوی |
| POST | `/api/v2/sharing/public-link/edit/{id}/` | ویرایش لینک | قوی |
| DELETE | `/api/v2/sharing/public-link/delete/{id}/` | حذف لینک | قوی |
| POST | `/api/v4/sharing/short-public-link/create/{id}/` | لینک کوتاه | قوی |
| GET | `/api/v4/sharing/get-shared-object/{id}/` | جزئیات اشتراک | قوی |
| GET | `/api/v3/sharing/list-shared-objects/` | فهرست اشتراک | قطعی |
| POST | `/api/v2/sharing/set-permission/` | مجوز دسترسی | قوی |
| POST | `/api/v2/sharing/unshare-object/{id}/` | لغو اشتراک | قوی |
| POST | `/api/v2/favorite/create-favorite/` | `obj_ids` | قطعی |
| POST | `/api/v2/favorite/delete-favorite/` | `obj_ids` | قطعی |

## URL upload، برچسب، نظر و جست‌وجو

| روش | مسیر | کارکرد | اطمینان |
|---|---|---|---|
| POST | `/api/v2/storage/url-add/` | بارگذاری از URL؛ `url`, `parent` | قطعی |
| GET | `/api/v2/storage/list-url-adds/` | فهرست URL upload | قطعی |
| DELETE | `/api/v2/storage/delete-url-storage/{id}/` | حذف مورد | قوی |
| GET | `/api/v1/flat/tag/list/` | فهرست برچسب | قطعی |
| POST | `/api/v1/flat/tag/create/` | ساخت برچسب | قطعی |
| POST | `/api/v1/flat/tag-membership/create/{id}/` | افزودن برچسب | قوی |
| DELETE | `/api/v1/flat/tag-membership/delete/{id}/` | حذف برچسب | قوی |
| POST | `/api/v1/comment/create-comment/{id}/` | `text` | قطعی |
| PATCH | `/api/v1/comment/update-comment/{id}/` | `text` | قوی |
| DELETE | `/api/v1/comment/delete-comment/{id}/` | حذف نظر | قوی |
| GET | `/api/v1/comment/list-object-comments/{id}/` | نظرات فایل | قوی |
| GET | `/api/v2/reporting/search-objects/` | جست‌وجوی فایل | قطعی |
| GET | `/api/v3/reporting/search-shared-objects/` | جست‌وجوی اشتراک | قطعی |
| POST | `/api/v3/reporting/search-history/create/` | ثبت تاریخچه | قوی |
| GET | `/api/v3/reporting/search-history/list/` | فهرست تاریخچه | قطعی |
| DELETE | `/api/v3/reporting/search-history/delete/` | حذف تاریخچه | قوی |
| GET | `/api/v2/reporting/suggest-objects/` | پیشنهاد recent/weekly/monthly | قطعی |
| GET | `/api/v1/flat/list-duplicated-objects/` | فایل‌های تکراری | قطعی |

## تنظیمات، نسخه، پلن و مخزن عمومی

| روش | مسیر | کارکرد | اطمینان |
|---|---|---|---|
| GET | `/api/v1/configuration/list-configs/` | تنظیمات اپ | قطعی |
| GET | `/api/v1/configuration/list-web-configs/` | تنظیمات وب | قطعی |
| GET | `/api/v1/versioning/check-version/{flavor}/` | بررسی نسخه | قطعی |
| POST | `/api/v2/versioning/check-signature/` | بررسی امضا | قوی |
| GET | `/api/v4/plan/list-purchases/` | خریدهای فعال | قطعی |
| GET | `/api/v1/public-repository/category/list/` | دسته‌های عمومی | قطعی |
| POST | `/api/v1/public-repository/public-object/list/` | اشیای عمومی | قطعی |

مدل‌های antivirus و policy نیز در DEX وجود دارند، اما مسیرهای کاملشان با اطمینان کافی به دست نیامد؛ بنابراین endpoint ساختگی برایشان درج نشده است.

