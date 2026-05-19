⚡ Flexy — High-Velocity Bidding Platform

> Bid. Win. Own. — A real-time auction platform built for speed.

Flexy is a full-stack live auction web app where users bid on products in real time. Auctions have live countdowns, bids update instantly across all connected users, and winners get a seamless checkout flow the moment the hammer falls.



🖼️ Pages at a Glance

| Page | What it does |
|---|---|
| **Dashboard** | Browse live, upcoming, and ended auctions by category |
| **Live Auction** | Real-time bidding with live countdown and bid feed |
| **Wishlist** | Save auctions with the ❤️ button; remove without reloading |
| **Order Checkout** | Winner fills address + picks Online or Cash on Delivery |
| **My Orders** | Track every order you've won |
| **Wallet** | Top up via Razorpay; balance used for bidding |
| **Notifications** | Real-time alerts — outbid, won, auction ended |
| **Settings** | Profile, password, and two-factor auth |


✨ Key Features

🔴 Live Auctions
- Countdown timers tick in real time across every browser simultaneously
- Bids reflect instantly to all connected users via WebSockets — no refresh needed
- Auction auto-closes when the timer hits zero; winner is notified immediately

❤️ Wishlist
- Heart button on every auction card — one click to save, one click to remove
- Dedicated wishlist page shows all saved items with live countdowns
- Removing an item animates it out instantly without a page reload

📦 Order Flow
- The moment an auction ends, the winner sees a **"Complete Your Order"** button
- Order page shows the product, image, and winning bid amount
- Fill in delivery address and choose: **Online Payment** (Razorpay / Wallet) or **Cash on Delivery**

💳 Wallet & Payments
- Top up your wallet using Razorpay (cards, UPI, net banking)
- Wallet balance is deducted atomically when you win — no double charges
- Every transaction logged in a personal ledger

🔐 Auth & Security
- Email OTP verification on signup
- Forgot password via email reset link
- Optional **two-factor authentication** (Google Authenticator / Authy)
- Account auto-locks after 5 failed login attempts
- View and revoke active sessions from any device

⚡ Performance
- Pages navigate fast — auth is cached locally for 60 seconds, no repeated server round-trips
- Dashboard loads sections in parallel (live, upcoming, popular, ended all at once)
- Skeleton shimmer cards shown while data arrives so nothing ever looks blank
- CSS and JS cached in browser for 7 days after first visit
- All responses gzip-compressed — 60–80% smaller on the wire



🛠️ Tech Stack

| | |
|---|---|
| **Backend** | Python, Flask, Flask-SocketIO |
| **Database** | Supabase (PostgreSQL) |
| **Real-time** | WebSockets via Flask-SocketIO + eventlet |
| **Payments** | Razorpay |
| **Auth** | bcrypt, HttpOnly cookies, pyotp (TOTP 2FA) |
| **Frontend** | Vanilla JS, HTML5, CSS3 |
| **Deployment** | Render.com |



🚀 Getting Started

Prerequisites
- Python 3.11+
- A [Supabase](https://supabase.com) project
- A Gmail account (for OTP emails)
- A [Razorpay](https://razorpay.com) account (optional — for payments)

1. Clone the repo
```bash
git clone https://github.com/SisiraReddy/flexy.git
cd flexy
```

 2. Set up Supabase
1. Create a project at [supabase.com](https://supabase.com)
2. Open **SQL Editor** → paste and run `backend/supabase_schema.sql`
3. Go to **Settings → API** and copy your **Project URL** and **service_role key**

3. Configure environment
```bash
cd backend
cp .env.example .env
```
Open `.env` and fill in:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
RAZORPAY_KEY_ID=rzp_test_xxxx
RAZORPAY_KEY_SECRET=xxxx
SECRET_KEY=any-long-random-string
FRONTEND_URL=http://localhost:5000
```

4. Install & run
```bash
pip install -r requirements.txt
python app.py
```
Open **http://localhost:5000**

5. Load demo data
```bash
python seed.py
```
This creates **100 auctions** (live, upcoming, and ended) with fresh timestamps and a demo account:

| | |
|---|---|
| **Email** | `demo@flexy.in` |
| **Password** | `Demo@1234` |

> Re-run `seed.py` any time to reset auction data with fresh timestamps.

---

☁️ Deploying to Render

Flexy uses WebSockets for live bidding — **Render.com** is the recommended host because it supports persistent connections. Vercel does not (serverless functions can't hold WebSockets open).

1. Push your code to GitHub
2. Place `render.yaml` in the repo root (same level as the `Flexy/` folder)
3. Go to **Render → New → Blueprint** and connect your repo
4. Add your environment variables in the Render dashboard
5. Deploy — then open the **Shell** tab and run `python seed.py`

---

📁 Project Structure

```
Flexy/
├── backend/
│   ├── app.py              # Flask app + all routes
│   ├── database.py         # Supabase HTTP client
│   ├── seed.py             # Demo data loader
│   ├── supabase_schema.sql # Run this once in Supabase
│   ├── models/             # Database logic per feature
│   ├── routes/             # API blueprints
│   ├── middleware/         # Auth guard, validation, rate limiting
│   └── services/           # Email, MFA
└── frontend/
    ├── static/
    │   ├── css/            # Per-page stylesheets + design tokens
    │   └── js/             # Per-page scripts + shared nav
    └── templates/          # 13 HTML pages
```

📬 Gmail Setup (for OTP emails)

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. **Security → 2-Step Verification** — turn it ON
3. **Security → App Passwords** → Create → name it `Flexy`
4. Paste the 16-character password into `MAIL_PASSWORD` in your `.env`

---

📄 License

MIT — free to use, modify, and build on.
=======
Flexy-A-Bidding-Platform
>>>>>>> d38d1032b193c9d8a6e7b05d0a3626e7e3e1e563
