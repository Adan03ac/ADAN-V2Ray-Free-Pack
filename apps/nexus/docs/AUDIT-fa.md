> این گزارش ثبت مرحلهٔ تثبیت قبلی است. برای وضعیت فعلی ادغام ریپو و بررسی Docker/مرورگر، `REPOSITORY-INTEGRATION.md` و آخرین اجرای `Nexus verification` را ببینید.

# ADAN NEXUS | CONNECT — گزارش ممیزی و تثبیت

تاریخ: ۱۴ نوامبر ۲۰۲۶ / ۲۳ آبان ۱۴۰۵

این خروجی ادامهٔ همان پروژهٔ Freebuff است. بازنویسی انجام نشده و کدی از BYVE وارد نشده است. این تحویل، ممیزی و یک مرحلهٔ تثبیت محلی است؛ تأیید آمادگی انتشار عمومی نیست.

## مبنا و روش بررسی

فایل پیوست با نام `adan-nexus-source(1).zip` دریافت شد. شناسهٔ محتوای مبنا:

```
SHA256: ac80a6dc78b500b27d888e2b79cdff55fcc011e4700fd2bc20bab15949abe436
```

آرشیو ۱۶۱ ورودی داشت. مسیرها قبل از استخراج برای traversal و symlink بررسی شدند. ساختار کامل در `evidence/source-inventory.json` ثبت شده است. آرشیو اصلی بدون تغییر در `rollback/original-source.zip` داخل ZIP تحویلی قرار دارد. فایل `.git` موجود در آرشیو به worktree محیط سازنده اشاره می‌کرد؛ برای توسعهٔ حاضر از آن استفاده نشد.

بررسی شامل مسیرهای API، dependencyهای authentication/authorization، مدل‌های SQLAlchemy، migration اولیه، parserهای پنج پروتکل، adapterها، fetcher، ingestion، publisher، worker/scheduler، health engine، frontend و مسیر proxy، فایل lock و Dockerfile/Compose بود. نصب Python در venv جدا و frontend با `npm ci --ignore-scripts` انجام شد. تست‌های جدید برای منابع شبکه از DNS، HTTP و socketهای شبیه‌سازی‌شده استفاده می‌کنند. smoke test واقعی فقط روی loopback و با SQLite و اطلاعات موقت انجام شد.

## نتیجهٔ اجرایی

| بررسی | نتیجه | شاهد |
|---|---|---|
| تست‌های نسخهٔ اولیه | ۶۳ پاس، ۲ شکست | `evidence/baseline-pytest.txt` و XML |
| علت دو شکست اولیه | وابستگی source CRUD و آزمون URL عمومی به DNS خارجیِ در دسترس‌نبودن در محیط | همان گزارش اولیه |
| تست‌های نسخهٔ اصلاح‌شده | ۱۰۵ پاس؛ ۵ هشدار deprecation | `evidence/pytest.txt` و `pytest.xml` |
| TypeScript | پاس | `evidence/typecheck.txt` |
| Next.js production build | پاس | `evidence/frontend-build.txt` |
| اجرای واقعی محلی | ۱۷ بررسی پاس | `evidence/runtime-smoke.json` |
| Alembic upgrade روی SQLite خالی | پاس | `evidence/migrations.txt` |
| تطبیق migration و مدل‌ها | بدون عملیات جدید | همان فایل؛ `alembic check` |
| audit اولیهٔ npm | ۱ Critical و ۲ High در درخت dependency | `evidence/npm-audit-before.json` |
| audit نهایی npm | صفر مورد شناخته‌شده در زمان بررسی | `evidence/npm-audit-after.json` |
| audit اولیهٔ Python | ۳۰ رکورد advisory در چهار package؛ بعضی رکوردها تکراری‌اند | `evidence/python-audit-before.json` |
| audit نهایی Python | صفر مورد شناخته‌شده در dependencyهای حل‌شده | `evidence/python-audit-after.json` |
| سازگاری dependencyهای نصب‌شده | `pip check` پاس | بررسی محلی |
| Docker | فقط بررسی YAML و wiring؛ اجرا نشده | `evidence/compose-static-check.txt` |

صفر بودن نتیجهٔ scanner تضمین نبودن آسیب‌پذیری نیست. build موفق هم معادل تست تعامل مرورگر نیست. گزارش‌های فعلی وضعیت همین نسخه و همین محیط را نشان می‌دهند؛ registryها و advisoryها ممکن است تغییر کنند.

## یافته‌ها و اصلاحات به ترتیب اولویت

شدت‌های کد، ارزیابی این ممیزی‌اند و امتیاز رسمی CVSS نیستند. شدت dependencyها از scanner گرفته شده است.

| ID | شدت | مشکل تأییدشده | اقدام و وضعیت |
|---|---|---|---|
| SEC-01 | Critical در scanner | Next.js قدیمی با advisoryهای امنیتی شناخته‌شده | Next `15.5.29`، React/ReactDOM `19.0.9`؛ PostCSS مستقیم و transitive روی `8.5.33`؛ lock به‌روز، build/typecheck/audit پاس |
| SEC-02 | High | فاصلهٔ DNS validation و اتصال HTTP امکان rebinding می‌داد | اتصال به IP عمومی بررسی‌شده pin شد؛ Host و TLS SNI نام اصلی را حفظ می‌کنند، certificate verification خاموش نشده؛ proxy محیطی غیرفعال؛ تست rebinding و redirect پاس |
| SEC-03 | High | health engine می‌توانست کانفیگ واردشده را به مقصد داخلی TCP تست کند | مقصدهای non-global و IPv4-mapped مسدود؛ TCP پیش‌فرض خاموش؛ فقط CIDR عمومی صریحاً مجاز؛ اتصال به IP بررسی‌شده؛ socket واقعی در regressionها باز نمی‌شود |
| SEC-04 | High | read-only با شناسهٔ profile دیگران به preview/export می‌رسید | کنترل مالکیت مشترک برای lookupهای profile؛ admin همچنان دسترسی مدیریتی دارد؛ پاسخ غیرمجاز 404 |
| SEC-05 | High | ایجاد کاربر ادمین CSRF dependency نداشت | ایجاد کاربر با CSRF و نقش admin؛ logout هم به CSRF همان session محدود شد؛ read-only می‌تواند session خودش را ببندد |
| SEC-06 | High | کلید رمزگذاری بدون تنظیم صریح، در هر process/restart تصادفی بود | کلید پایدار حداقل ۳۲ کاراکتر در همهٔ محیط‌ها لازم؛ placeholderهای شناخته‌شده در production رد می‌شوند؛ فرمت Fernet و ciphertextهای موجود تغییر نکرد |
| SEC-07 | High | رمز ساخته‌شدهٔ bootstrap در stdout چاپ می‌شد | ساخت اولین ادمین نیازمند رمز صریح است؛ رمز تولید و چاپ نمی‌شود؛ اطلاعات حساب موجود بازنویسی نمی‌شود |
| SEC-08 | High | لینک منبع manual در API کامل نمایش داده می‌شد | ورودی جدید manual در همان ستون با prefix `nexus:fernet:` رمز می‌شود؛ API مقدار `<redacted>` می‌دهد؛ adapter لینک‌های plaintext قدیمی را هم می‌خواند |
| SEC-09 | High در dependency tree | Python runtime دارای advisoryهای شناخته‌شده در Cryptography و Starlette و dependencyهای دیگر بود | FastAPI `0.162.7`، Starlette `1.3.1`، Cryptography `50.0.2`، dotenv `1.2.2` و pytest `9.0.3`؛ regression، migration و audit پاس |
| SEC-10 | Medium | IP limiter از `X-Forwarded-For` خام خوانده می‌شد | identity از peer ASGI خوانده می‌شود؛ اعتماد به proxy فقط از تنظیم Uvicorn انجام می‌شود |
| SEC-11 | Medium | مسیر توکن public ممکن بود در لاگ slow/failing request ثبت شود | redaction مسیر subscription و share link در متن، context و exception formatter؛ مسیر middleware هم redacted |
| SEC-12 | Medium | bcrypt هنگام verify ورودی طولانی را truncate می‌کرد | رمز بیش از ۷۲ بایت رد می‌شود؛ hashهای موجود سازگارند |
| BUG-01 | High عملکردی | redirect بررسی می‌شد ولی `current_url` عوض نمی‌شد | مقصد واقعی دنبال می‌شود؛ بودجهٔ redirect و retry جدا؛ redirect داخلی مسدود؛ تست مقصد/loop/retry/size پاس |
| BUG-02 | High عملکردی | adapter عمومی، نوع manual را قبل از adapter مخصوص می‌گرفت و HTTP request می‌زد | ثبت نوع‌ها تفکیک شد؛ manual بدون fetch وارد pipeline می‌شود؛ فرمت دادهٔ قبلی خوانده می‌شود |
| BUG-03 | High عملکردی | شکست publisher یک run را در وضعیت running باقی می‌گذاشت | خطا terminal می‌شود؛ دادهٔ ingestشده نگه داشته می‌شود؛ تا یک ساعت pipeline را قفل نمی‌کند؛ regression پاس |
| BUG-04 | Medium | export JSON پس از شکست decryption، metadata و link را اشتباه pair می‌کرد | فقط زوج‌های موفق config/link صادر می‌شوند؛ regression روی خرابی ciphertext |
| BUG-05 | Medium | format override عمومی profile را موقتاً در DB commit می‌کرد | فرمت به renderer پاس داده می‌شود؛ profile ذخیره‌شده عوض نمی‌شود |
| BUG-06 | Medium | عنوان فارسی profile در header لاتین قابل ارسال نبود | `Profile-Title` به قالب `base64:` با UTF-8 تبدیل شد؛ پاسخ فارسی تست شده |
| BUG-07 | Medium | context managerِ DNS executor عملاً بعد از timeout منتظر resolver می‌ماند | pool و ظرفیت مشترک محدود؛ timeout سریع برمی‌گردد؛ resolver گیرکرده همچنان محدودیت معماری دارد |
| BUG-08 | Medium | تعداد jobهای همزمان health در process محدود نبود | همزمانی jobها به یک job در process محدود؛ درخواست اضافی 409؛ تعداد واقعی IDهای معتبر محاسبه می‌شود |
| BUG-09 | Medium | syntax-only وضعیت قبلی connectivity را unknown می‌کرد؛ QUIC با TCP سنجیده می‌شد | syntax-only وضعیت قبلی را نگه می‌دارد؛ TCP برای QUIC unavailable؛ failure latency فعلی را پاک می‌کند |
| BUG-10 | Medium | PATCH با null برای ستون اجباری به DB error می‌رسید | null برای فیلدهای اجباری 422؛ notes/description همچنان nullable |
| OPS-01 | High برای قابلیت اجرا | Dockerfile پوشهٔ `public` غایب را COPY می‌کرد | پوشه با `.gitkeep` اضافه شد؛ build واقعی Docker هنوز اجرا نشده |
| OPS-02 | Medium | backend و worker همزمان migration اجرا می‌کردند | migration در entrypoint backend؛ worker بعد از healthcheck backend شروع می‌شود؛ auto-create در worker/CLI تابع تنظیم شده |
| OPS-03 | Medium | frontend پیش‌فرض روی همهٔ interfaceها publish می‌شد | Compose پیش‌فرض روی `127.0.0.1`؛ تغییر bind باید انتخاب آگاهانهٔ اپراتور باشد |
| OPS-04 | Medium | startup بدون DNS منابع پیش‌فرض را seed نمی‌کرد | seeding فقط URL syntax/literal را بررسی می‌کند؛ fetch همچنان DNS و IP را در زمان درخواست بررسی می‌کند |
| OPS-05 | Medium | `%` در URL دیتابیس با interpolation Alembic ناسازگار بود | escaping برای ConfigParser؛ فرمت URL دیتابیس عوض نشده |

## وضعیت واقعی قابلیت‌ها

| قابلیت | وضعیت فعلی | حدود شواهد |
|---|---|---|
| session، admin/read-only، CSRF، lockout | پیاده‌سازی‌شده و تست‌شده | API regression و login/logout از proxy محلی؛ password reset/MFA موجود نیست |
| ingestion و provenance | پیاده‌سازی‌شده و تست‌شده با fixture | dedup تکراری، partial/total failure، manual و conditional handling؛ feed خارجی زنده بررسی نشده |
| parser پنج پروتکل | پیاده‌سازی‌شده و تست‌شده در سطح syntax | اعتبار UUID برای VLESS/VMess اضافه شد؛ همهٔ extensionهای کلاینت‌ها اعتبارسنجی نمی‌شوند |
| health | جزئی؛ syntax، DNS و TCP محدود | TCP فقط مقصد مجاز؛ worker هنوز در process API است، sandbox مستقل ندارد |
| تأیید VPN | پیاده‌سازی نشده | نه tunnel handshake، نه exit IP، نه end-to-end؛ مقدار verified-working همچنان صفر است |
| subscription | plain/base64/json و token revocation پیاده‌سازی و تست شده | بعضی accountingها write-on-read هستند؛ expiry UI و policy تکمیل نشده |
| publication محلی | پیاده‌سازی‌شده، جزئی تست‌شده | atomic در سطح هر فایل؛ کل مجموعهٔ فایل‌ها یک transaction اتمیک نیست |
| version history | جزئی | نام نسخه microsecond دارد و collision ثانیه‌ای رفع شده؛ retention فعلاً ۱۰ نسخه، API restore ندارد |
| audit و monitoring | جزئی | رویدادهای اصلی ثبت می‌شوند؛ write و audit در یک transaction نیستند؛ metricهای runtime کامل نیستند |
| local-first | جزئی | SQLite، manual ingestion، backup/restore و خاموش‌کردن شبکهٔ upstream؛ PWA/offline browser cache ندارد |
| backup/restore SQLite | جدید، پیاده‌سازی و تست‌شده | backup API SQLite، integrity check، permission 0600، مقصد جدید؛ overwrite رد می‌شود |
| backup/restore PostgreSQL | دستورالعمل؛ اجرا نشده | نیازمند تست روی stack واقعی |
| Docker self-hosting | پیکربندی اصلاح‌شده؛ اجرا نشده | daemon/CLI در این محیط موجود نبود |
| Cloudflare و GitHub push publisher | برنامه‌ریزی‌شده / stub | هیچ حساب یا سرویس واقعی متصل یا deploy نشده |
| CI | workflow اضافه‌شده | commandهای اصلی اینجا پاس شده‌اند؛ GitHub Actions خارجی اجرا نشده |

## باقی‌مانده‌ها و ریسک‌هایی که باید پیش از انتشار عمومی بسته شوند

### P1 — دروازهٔ انتشار عمومی

1. اجرای Compose و migration روی PostgreSQL واقعی و تست restart، failure، volume permissions، Redis outage و upgrade از دیتابیس موجود. تست‌های این تحویل از SQLite استفاده کرده‌اند.
2. انتقال health به worker مستقل با queue پایدار، policy مقصد در worker و egress policy سیستم‌عامل؛ مدیریت jobهای نیمه‌تمام بعد از crash. محدودیت یک job فعلی فقط در همان process برقرار است، بنابراین فعلاً API را با چند worker اجرا نکنید.
3. انتشار snapshot کامل با directory/version pointer اتمیک و تست crash بین نوشتن فایل‌ها. وضعیت فعلی per-file atomic است و هنگام خطا ممکن است root snapshot ترکیبی شود.
4. HTTPS، `COOKIE_SECURE=true`، origin دقیق، secrets واقعی خارج از سورس، Redis محافظت‌شده و proxy trust محدود روی محیط هدف. Secure cookie در HTTP محلی پیش‌فرض خاموش است؛ این پیش‌فرض برای انتشار عمومی مناسب نیست.
5. تست مرورگری نقش‌ها، فرم‌ها، فارسی/RTL، دانلود و cookieها. بررسی اینجا شامل HTML و مسیرهای HTTP بود، نه تعامل واقعی در browser.

### P2 — صحت و نگهداشت

- هویت dedup فعلی همهٔ پارامترهای عملیاتی پروتکل‌ها مثل برخی `flow`/`sid`/plugin optionها را در بر نمی‌گیرد و بعضی طول‌ها کوتاه می‌شوند؛ کانفیگ‌های متفاوت ممکن است یکی محسوب شوند. اصلاح با fingerprint نسخه‌بندی‌شده و migration کنترل‌شده انجام شود تا شناسه‌ها و provenance قبلی از بین نروند.
- همهٔ حالت‌های IPv6، cipherهای SS، Reality، authentication و semantics پروتکل‌ها کامل نیستند. syntax-valid به معنای client-compatible نیست.
- plaintext منابع manual قدیمی برای سازگاری هنوز در DB قدیمی می‌مانند؛ API آن‌ها را مخفی می‌کند. تبدیل گروهی آن‌ها به ciphertext پس از backup و migration برنامه‌ریزی شود. URL منابع HTTPS ممکن است query token داشته باشد؛ registry باید redaction و secret-reference جدا برای آن‌ها پیدا کند.
- timeout HTTP از نوع per-operation است، نه deadline کلی؛ stream بسیار کند می‌تواند worker ingestion را طولانی نگه دارد. سقف زمان کلی و decompression budget قبل از اتکا به منابع مهاجم اضافه شود.
- upstream status و GitHub history از HTTP client جدا استفاده می‌کنند؛ parity با fetcher محدود و pinشده، سقف payload و cache resilient لازم است. در حالت offline این مسیرها خاموش می‌شوند. هیچ token واقعی در این تحویل استفاده نشد.
- schemaهای health/settings باید محدودیت‌های config بیشتری داشته باشند. UI preferenceهای ذخیره‌شده عمدتاً موتور اجرا را تغییر نمی‌دهند؛ environment فعلاً authoritative است.
- Redis limiter هنگام قطع پس از startup خطا می‌دهد؛ fallback و سیاست fail-open/fail-closed باید مشخص و تست شوند. حافظهٔ limiter در حملهٔ high-cardinality سقف سخت ندارد.
- readiness فعلی cache را دقیق probe نمی‌کند و scheduler متعلق به process worker را از API نمی‌بیند. خطای DB هم همیشه HTTP status مناسب برای Docker readiness نمی‌دهد.
- logging redaction دفاع چندلایه است و جایگزین ندادن credential به متن خطاها نیست. access logهای reverse proxy هم باید مسیر subscription را redact کنند.
- metadata و ciphertext موجود حفظ شدند؛ هیچ migration مخرب اجرا نشد. برای تبدیل داده‌های قدیمی در مرحلهٔ بعد، compatibility test روی کپی DB واقعی لازم است.
- اصل least privilege برای roleهای بیشتر از admin/read-only، password change/reset، MFA، session inventory و audit transactionality تکمیل شود.
- API docs به‌خاطر CSP عمومی فعلی ممکن است در مرورگر درست نمایش داده نشود؛ schema JSON قابل دریافت است. CSP جداگانه برای docs و frontend بررسی شود.

### P3 — توسعهٔ محصول

- agent مجاز برای protocol handshake و end-to-end، با هویت region واقعی و consent؛ بدون تبدیل DNS/TCP به ادعای VPN سالم.
- subscription version/restore، TTL، policy مالکیت token بعد از deactivate، usage accounting و محدودیت درخواست عمومی.
- local-first browser/PWA، export/import تنظیمات و backup زمان‌بندی‌شدهٔ رمزگذاری‌شده با آزمون بازیابی.
- providerهای انتشار خارجی فقط بعد از تست، credentialهای محدود و تأیید جداگانه؛ Cloudflare و GitHub push فعلاً stub بمانند.

## نقشهٔ راه پیشنهادی

| مرحله | خروجی | معیار عبور |
|---|---|---|
| انجام‌شده: Audit + Stabilization 1 | اصلاحات این گزارش، regression، build، migration و smoke محلی، ZIP و baseline | شواهد `evidence/`؛ ۱۰۵ تست پاس |
| بعدی: Deployment Verification | Compose روی میزبان آزمایشی، PostgreSQL/Redis، TLS و backup drill | clean install + upgrade + restart + restore؛ عدم دسترسی عمومی قبل از تأیید |
| بعدی: Reliable Workers | queue پایدار، health agent جدا، global limits و recovery | crash/retry/cancel و policy egress تست‌شده |
| بعدی: Data Correctness | fingerprint v2، parser semantics، source timeout و secret migration | مهاجرت روی کپی دادهٔ واقعی بدون از دست‌رفتن provenance |
| بعدی: Publication + Operations | snapshot pointer اتمیک، restore، readiness و audit تراکنشی | crash tests، rollback و restore end-to-end |
| بعدی: Product Completion | local-first UI، roleهای بیشتر، E2E agent و providerها | acceptance test برای هر قابلیت؛ اقدامات خارجی نیازمند تأیید |

## اجرای مجدد بررسی‌ها

از ریشهٔ پروژه:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/python -m pytest -q --junitxml=../evidence/pytest.xml
cd ../frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
NEXT_TELEMETRY_DISABLED=1 npm run build
npm audit --audit-level=high
```

تست‌ها متغیرهای محیطی مخصوص خودشان را پیش از import برنامه تنظیم می‌کنند. برای اجرای واقعی، `.env` محلی با کلید پایدار لازم است. ابزار audit Python جزو runtime محصول نیست؛ جدا نصب و اجرا شود. اطلاعات freeze محیط در `evidence/environment-freeze.txt` شامل ابزار ممیزی هم هست و جایگزین `backend/requirements.txt` نیست.

راهنمای اجرا، backup و Docker: `docs/DEPLOYMENT.md`.

## مراجع امنیتی بیرونی

این مراجع برای انتخاب نسخه و تطبیق advisory بررسی شدند؛ نتیجهٔ قابل بازتولید همین build در JSONهای audit ثبت است.

- https://github.com/vercel/next.js/security/advisories
- https://github.com/vercel/next.js/security/advisories/GHSA-f3mh-rxg3-f5g2
- https://react.dev/blog/2025/12/03/critical-security-vulnerability-in-react-server-components
- https://github.com/react/react/security/advisories/GHSA-h3gv-c5rc-p453

هیچ اسکن آزاد شبکه، آزمون VPN واقعی، استفاده از credential واقعی، تغییر زیرساخت دارای دسترسی ویژه یا انتشار عمومی انجام نشد.
