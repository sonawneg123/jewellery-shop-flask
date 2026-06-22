# Aurum Jewellery Shop — Deployment Guide
## Three-Tier Architecture: Nginx → Flask/Gunicorn → AWS RDS MySQL

```
Internet
    │
    ▼
[ Nginx ] ← reverse proxy, TLS, rate limiting, static files
    │
    ▼  /api/*
[ Gunicorn + Flask ]  ← Python application server
    │
    ▼
[ AWS RDS MySQL 8.0 ]  ← managed database
```

---

## 1. AWS RDS Setup

1. Create an RDS MySQL 8.0 instance in your VPC.
2. Set **DB name** = `jewellery_shop`, note the endpoint, username, password.
3. Allow inbound port **3306** from your EC2 security group only.
4. Load the schema:

```bash
mysql -h YOUR_RDS_ENDPOINT -u admin -p < db/test.sql
```

---

## 2. EC2 Server Setup (Ubuntu 22.04+)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx
```

---

## 3. Backend Deploy

```bash
# Clone / upload project to /var/www/jewellery_shop
cd /var/www/jewellery_shop/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env    # fill in DB_HOST, DB_USER, DB_PASSWORD, SECRET_KEY, JWT_SECRET_KEY
```

### Gunicorn systemd service

Create `/etc/systemd/system/jewellery_shop.service`:

```ini
[Unit]
Description=Aurum Jewellery Shop — Flask/Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/jewellery_shop/backend
Environment="PATH=/var/www/jewellery_shop/backend/venv/bin"
EnvironmentFile=/var/www/jewellery_shop/backend/.env
ExecStart=/var/www/jewellery_shop/backend/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:5000 \
    --timeout 60 \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile  /var/log/gunicorn/error.log \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/log/gunicorn
sudo chown www-data:www-data /var/log/gunicorn
sudo systemctl daemon-reload
sudo systemctl enable --now jewellery_shop
sudo systemctl status jewellery_shop
```

---

## 4. Nginx Reverse Proxy

```bash
# Copy nginx config
sudo cp nginx/jewellery_shop.conf /etc/nginx/sites-available/jewellery_shop
sudo ln -s /etc/nginx/sites-available/jewellery_shop /etc/nginx/sites-enabled/

# Edit domain name in the config
sudo nano /etc/nginx/sites-available/jewellery_shop
# → Replace `yourdomain.com` with your actual domain

# Get TLS certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test & reload
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Frontend Deploy

```bash
sudo mkdir -p /var/www/jewellery_shop/frontend
sudo cp frontend/index.html /var/www/jewellery_shop/frontend/
sudo chown -R www-data:www-data /var/www/jewellery_shop/frontend
```

> **Important:** The frontend calls `/api/*` — Nginx proxies those to Flask.  
> Update `const API = '/api'` in `index.html` if your setup differs.

---

## 6. Project Structure

```
jewellery_shop/
├── db/
│   └── test.sql              ← Full MySQL schema + seed data
├── backend/
│   ├── app.py                ← Flask application
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── index.html            ← Single-page luxury UI
└── nginx/
    └── jewellery_shop.conf   ← Nginx reverse proxy config
```

---

## 7. API Reference

| Method | Endpoint                        | Auth | Description                  |
|--------|---------------------------------|------|------------------------------|
| POST   | /api/auth/register              | ✗    | Register new client          |
| POST   | /api/auth/login                 | ✗    | Login, returns JWT           |
| GET    | /api/auth/profile               | ✓    | Get client profile           |
| PUT    | /api/auth/profile               | ✓    | Update profile               |
| GET    | /api/categories                 | ✗    | List jewellery categories    |
| GET    | /api/items                      | ✗    | Catalogue with live prices   |
| GET    | /api/items?category_id=1        | ✗    | Filter by category           |
| GET    | /api/items?search=ring          | ✗    | Search items                 |
| GET    | /api/prices                     | ✗    | Live metal prices            |
| GET    | /api/cart                       | ✓    | View cart                    |
| POST   | /api/cart/add                   | ✓    | Add item to cart             |
| PUT    | /api/cart/update/{id}           | ✓    | Update item quantity         |
| DELETE | /api/cart/remove/{id}           | ✓    | Remove cart item             |
| DELETE | /api/cart/clear                 | ✓    | Clear entire cart            |
| POST   | /api/orders                     | ✓    | Place order from cart        |
| GET    | /api/orders                     | ✓    | View order history           |
| GET    | /api/health                     | ✗    | Health check                 |

---

## 8. Key Features

- **Real-time prices** — Metal prices stored in DB, refreshed via API; item prices calculated dynamically as `(weight × price/gram) + making charges + stone charges`
- **Budget tracker** — Visual progress bar in cart shows how much of the client's budget is used
- **JWT auth** — Stateless, 12-hour tokens; stored in `localStorage`
- **Rate limiting** — Nginx limits auth to 10 req/min, API to 30 req/min
- **Security headers** — HSTS, X-Frame-Options, CSP via Nginx
- **DB views** — `vw_item_prices` and `vw_cart_summary` for quick reporting queries
