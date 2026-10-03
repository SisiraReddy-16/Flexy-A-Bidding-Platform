# ⚡ Flexy — High-Velocity Bidding Platform

**Bid. Win. Own.** — A real-time auction platform built for speed.

Flexy is a full-stack live auction web app where users bid on products in real time. Auctions have live countdowns, bids update instantly across all connected users, and winners get a seamless checkout flow the moment the hammer falls.


## 🖼️ Pages at a Glance

| Page | What it does |
|---|---|
| Dashboard | Browse live, upcoming, and ended auctions by category |
| Live Auction | Real-time bidding with live countdown and bid feed |
| Wishlist | Save auctions with the ❤️ button; remove without reloading |
| Order Checkout | Winner fills address + picks Online or Cash on Delivery |
| My Orders | Track every order you've won |
| Wallet | Top up via Razorpay; balance used for bidding |
| Notifications | Real-time alerts — outbid, won, auction ended |
| Settings | Profile, password, and two-factor auth |

## ✨ Key Features

### 🔴 Live Auctions
- Countdown timers tick in real time across every browser simultaneously
- Bids reflect instantly to all connected users via WebSockets (Socket.IO) — no refresh needed
- Auction auto-closes when the timer hits zero; winner is notified immediately

### ❤️ Wishlist
- Heart button on every auction card — one click to save, one click to remove
- Dedicated wishlist page shows all saved items with live countdowns
- Removing an item animates it out instantly without a page reload

### 📦 Order Flow
- The moment an auction ends, the winner sees a "Complete Your Order" button
- Order page shows the product, image, and winning bid amount
- Fill in delivery address and choose: Online Payment (Razorpay / Wallet) or Cash on Delivery

### 💳 Wallet & Payments
- Top up your wallet using Razorpay (cards, UPI, net banking)
- Wallet balance is deducted when you bid / pay — no double charges
- Every transaction logged in a personal ledger

### 🔐 Auth & Security
- Email OTP verification on signup
- Forgot password via email reset link
- Optional two-factor authentication (Google Authenticator / Authy)
- Account auto-locks after 5 failed login attempts
- View and revoke active sessions from any device

### ⚡ Performance
- Pages navigate fast — auth is cached locally for 60 seconds
- Dashboard loads sections in parallel (live, upcoming, popular, ended)
- Skeleton shimmer cards shown while data arrives
- CSS and JS cached in browser for 7 days; responses gzip-compressed

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Java 17, Spring Boot 3 |
| Database | Supabase (PostgreSQL) via REST |
| Real-time | WebSockets via Socket.IO (netty-socketio) |
| Payments | Razorpay |
| Email | Brevo API |
| Auth | bcrypt (Spring Security Crypto), HttpOnly cookies, TOTP 2FA (built-in + ZXing QR) |
| Frontend | Vanilla JS, HTML5, CSS3 |
| Build | Maven |
| Deployment | Docker / Render.com |

## 🚀 Getting Started

### Prerequisites
- JDK 17+
- Maven 3.9+
- A Supabase project
- A Brevo account (for OTP emails)
- A Razorpay account (optional — for payments)


## 📁 Project Structure

```
Flexy/
├── pom.xml                      # Maven build
├── Dockerfile / render.yaml     # Deployment
├── .env 
└── src/main/
    ├── java/in/flexy/
    │   ├── Application.java         # Spring Boot entry point
    │   ├── WebController.java       # Pages, static files, /health, admin seed
    │   ├── AuthController.java      # Signup, login, OTP, MFA, sessions
    │   ├── AuctionController.java   # Auctions + bidding
    │   ├── WalletController.java    # Wallet + Razorpay
    │   ├── UserController.java      # Profile, stats, KYC
    │   ├── MiscControllers.java     # Notifications, watchlist, orders
    │   ├── SocketService.java       # Live bidding (Socket.IO)
    │   ├── Store.java               # Database logic per feature
    │   ├── Db.java                  # Supabase HTTP client
    │   ├── Auth.java / Util.java    # Auth guard, validation, rate limiting
    │   ├── Mail.java / Mfa.java     # Email (Brevo), two-factor auth
    │   └── Seeder.java              # Demo data loader
    └── resources/
        ├── application.properties
        ├── flexy_bidding_dataset.csv
        └── frontend/
            ├── static/{css,js}      # Per-page stylesheets + scripts
            └── templates/           # 13 HTML pages
```
