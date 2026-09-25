# ONLINE PARKING SLOT RESERVATION AND MANAGEMENT SYSTEM

A full-stack web application developed with **Python 3**, **Django**, **MySQL**, **Bootstrap 5**, and **Vanilla JavaScript** for an 8-week Python Full Stack Internship project.

---

## 📌 Project Overview

### Problem
In conventional parking facilities, drivers must reach the facility first and search for an available parking space. This creates congestion, delay, and uncertainty.

### Solution
**ParkEase** provides a self-service reservation platform where customers can check parking slot availability for any future date and time window, choose their preferred slot from a visual floor grid, enter vehicle details, calculate parking fees, complete a demo payment simulation, and receive a booking confirmation with a unique Booking ID.

An integrated **Admin Dashboard** provides facility operators with full control over parking slots (CRUD), pricing configuration, vehicle check-in/check-out, customer history, payment logs, and basic operational/financial reports.

---

## 🚀 Key Architectural Highlights & Business Rules

1. **Single Source of Truth for Pricing**:
   - `Pricing` model stores hourly rates per vehicle type (`CAR` → ₹30/hour, `BIKE` → ₹15/hour).
   - Admin manages rates in one central place.
2. **Dynamic Slot Availability (No Permanent Slot Status)**:
   - `ParkingSlot` stores physical slot metadata only (`slot_number`, `vehicle_type`, `is_active`).
   - Slot availability is calculated dynamically on the fly from existing reservations:
     $$\text{Overlap} \iff (\text{new\_start} < \text{existing\_end}) \land (\text{new\_end} > \text{existing\_start})$$
   - Only `CONFIRMED` and `ACTIVE` bookings block a slot. `PENDING_PAYMENT` bookings do not block slots permanently.
3. **Vehicle Double-Booking Prevention**:
   - A single vehicle registration number cannot have multiple overlapping bookings during the same time window.
4. **Demo Payment Simulation**:
   - Clear demo payment interface (UPI, Card, Cash) without fake financial graphics.
5. **Admin Operations with Django Authentication**:
   - Staff-protected views using `@staff_member_required`.
   - Live **current database-based parking metrics** (Total slots, currently available, booked, occupied, today's bookings, today's recorded revenue).
   - **Check-In**: `CONFIRMED` ➔ `ACTIVE` (Records check-in timestamp).
   - **Check-Out**: `ACTIVE` ➔ `COMPLETED` (Records check-out timestamp).

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Backend Framework** | Python 3.10+ / Django 5.0+ |
| **Database** | MySQL (with zero-config SQLite fallback for local evaluation) |
| **Database Driver** | PyMySQL (`pymysql.install_as_MySQLdb()`) |
| **Frontend Framework** | Bootstrap 5.3.3 & Bootstrap Icons |
| **Styling & UI** | Custom CSS3 (`custom.css`), Responsive Flexbox/Grid |
| **Client Scripts** | Vanilla JavaScript (ES6+) |
| **Authentication** | Django built-in `django.contrib.auth` (Admin only) |

---

## 📂 Project Structure

```text
parking_management_system/
│
├── manage.py
├── requirements.txt
├── README.md
│
├── parking_system/
│   ├── __init__.py          # PyMySQL integration
│   ├── settings.py          # Database & app configuration
│   ├── urls.py              # Root routing
│   ├── wsgi.py & asgi.py
│
├── parking/
│   ├── admin.py             # Django admin model registrations
│   ├── forms.py             # Availability, customer, payment, slot forms
│   ├── models.py            # ParkingSlot, Pricing, Booking, Payment
│   ├── tests.py             # 7 automated test suites
│   ├── urls.py              # Customer and admin URL patterns
│   ├── utils.py             # Availability engine, vehicle validation, pricing logic
│   ├── views.py             # Customer & Admin business controllers
│   └── management/commands/
│       └── seed_data.py     # Automated sample data & admin creator
│
├── static/
│   ├── css/custom.css       # Visual bays, badges, printable voucher styling
│   └── js/main.js           # Payment switcher & form helpers
│
└── templates/
    ├── base.html            # Master layout with navbar & footer
    ├── home.html            # Public landing page
    ├── booking/
    │   ├── check_availability.html  # Date/Time selector & visual slot layout
    │   ├── customer_details.html    # Vehicle & customer input form
    │   ├── review_booking.html      # Pre-payment verification summary
    │   ├── payment.html             # Demo payment simulation
    │   ├── confirmation.html        # Printable parking voucher
    │   └── check_booking.html       # Booking lookup & cancellation
    └── admin/
        ├── admin_nav.html           # Admin sub-navigation bar
        ├── login.html               # Staff login portal
        ├── dashboard.html           # Current database-based parking metrics & actions
        ├── slots.html               # Parking slots table
        ├── slot_form.html           # Slot add/edit form
        ├── pricing.html             # Hourly pricing configuration
        ├── bookings.html            # Searchable bookings ledger
        ├── booking_detail.html      # Detailed booking audit view
        ├── customers.html           # Aggregated customer directory
        ├── payments.html            # Transaction audit log
        └── reports.html             # Daily & Monthly report summaries
```

---

## ⚙️ Installation & Setup Guide

### 1. Prerequisites
- Python 3.10+ installed
- MySQL Server (optional for MySQL mode, e.g. MySQL 8.0 or XAMPP)

### 2. Create and Activate Virtual Environment

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🗄️ Database Configuration

### Option A: MySQL Configuration
1. Create a MySQL database:
```sql
CREATE DATABASE parking_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
2. Set environment variables:
```bash
# Windows PowerShell
$env:DB_ENGINE="mysql"
$env:DB_NAME="parking_db"
$env:DB_USER="root"
$env:DB_PASSWORD="your_password"
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
```

### Option B: Zero-Config SQLite (Default Quick Run)
If MySQL environment variables are not set, the app runs automatically on SQLite with zero setup.

---

### 4. Run Migrations & Seed Data
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data
```

**Default Admin Credentials:**
- **Username:** `admin`
- **Password:** `admin123`
- **Login URL:** `http://127.0.0.1:8000/admin-login/`

### 5. Start Development Server
```bash
python manage.py runserver
```

Open your browser:
👉 **`http://127.0.0.1:8000/`**

---

## 🧪 Automated Testing

Run the test suite:
```bash
python manage.py test
```

### Test Cases Covered:
1. `test_01_pricing_and_duration_calculation`: Accurate fee calculation from central `Pricing` model.
2. `test_02_availability_search_form_validations`: Past date and invalid time rejection.
3. `test_03_time_overlap_and_pending_expiration`: Overlapping time rejection and non-blocking `PENDING_PAYMENT`.
4. `test_04_vehicle_overlap_prevention`: Prevents overlapping bookings for the same vehicle.
5. `test_05_full_customer_booking_and_payment_flow`: Complete customer journey.
6. `test_06_booking_cancellation_and_slot_release`: Validates cancellation and instant slot release.
7. `test_07_admin_auth_and_check_in_out`: Staff permissions and check-in / check-out status transitions.
