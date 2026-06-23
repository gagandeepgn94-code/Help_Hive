# 🐝 HelpHive — Community Emergency Response Platform

> **Real-time, AI-powered emergency support connecting people with verified volunteers — doctors, nurses, blood donors, fire rescue teams, and NGO workers.**

[![Flask](https://img.shields.io/badge/Flask-3.1.3-000?logo=flask)](https://flask.palletsprojects.com/)
[![AWS DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-232F3E?logo=amazondynamodb)](https://aws.amazon.com/dynamodb/)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA-NIM_AI-76B900?logo=nvidia)](https://build.nvidia.com/)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-4.7.5-010101?logo=socketdotio)](https://socket.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](#)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [API Routes](#-api-routes)
- [AI Engine](#-ai-engine)
- [Database Schema](#-database-schema)
- [Pages & Screenshots](#-pages--screenshots)
- [Contributors](#-contributors)

---

## 🌟 Overview

**HelpHive** is a location-based emergency response platform built as a PBL (Project-Based Learning) project at **GM University**. When someone faces an emergency — a medical crisis, fire, or need for blood — they submit a request through HelpHive. The platform uses **AI-powered triage** to assess severity, finds **nearby volunteers** using GPS-based matching, and sends **real-time alerts** via Socket.IO and **SMS notifications** via AWS SNS.

### How It Works

```
1. 🚨 User submits emergency request with location
2. 🧠 AI engine analyzes severity and recommends search radius
3. 📍 System finds nearby volunteers by category and distance
4. 🔔 Volunteers receive real-time dashboard alerts + SMS
5. ✅ Volunteer accepts and responds to the emergency
```

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🚨 **Emergency Request System** | Users submit categorized requests with GPS auto-detection and reverse geocoding |
| 🧠 **AI-Powered Triage** | NVIDIA NIM LLM predicts priority, severity score, confidence, and optimal search radius |
| 📍 **Smart Volunteer Matching** | Haversine distance calculation with AI-recommended radius and adaptive tier expansion |
| 🔔 **Real-Time Notifications** | Socket.IO pushes live toast alerts to volunteer dashboards instantly |
| 📱 **SMS Alerts** | AWS SNS sends emergency SMS to volunteers' phones |
| 🗺️ **Interactive Live Map** | Leaflet.js dark-themed map showing volunteer position and emergency markers |
| 📊 **Analytics Dashboards** | Per-volunteer and global admin dashboards with Chart.js (doughnut, bar, polar area) |
| 🔐 **Secure Authentication** | bcrypt password hashing, session management, 7-day "Remember Me" |
| 🏥 **Cross-Category Matching** | Doctors can see Nurse requests and vice versa |
| 📈 **AI Insights on Dashboard** | Every request card shows AI Priority, Severity, Confidence, Radius, and Reason |

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3** | Core language |
| **Flask 3.1.3** | Web framework |
| **Flask-SocketIO** | Real-time WebSocket events |
| **boto3** | AWS SDK for DynamoDB and SNS |
| **bcrypt** | Password hashing |
| **requests** | HTTP client for NVIDIA API |

### Frontend
| Technology | Purpose |
|---|---|
| **HTML5 / CSS3 / JavaScript** | Core web technologies |
| **Jinja2** | Server-side templating |
| **Chart.js 4.4** | Dashboard chart visualizations |
| **Leaflet.js** | Interactive emergency map |
| **Socket.IO Client 4.7.5** | Real-time event handling |
| **Font Awesome 6.5** | Icon library |
| **Google Fonts (Outfit)** | Typography |

### Cloud & AI
| Technology | Purpose |
|---|---|
| **AWS DynamoDB** | NoSQL database for volunteers and requests |
| **AWS SNS** | SMS notifications to volunteers |
| **NVIDIA NIM API** | LLM-based emergency triage (meta/llama-3.2-3b-instruct) |
| **Nominatim (OpenStreetMap)** | Reverse geocoding (GPS → address) |
| **CartoDB** | Dark map tile provider |

### Design
| Pattern | Implementation |
|---|---|
| **Dark Mode** | Exclusive dark theme with curated color palette |
| **Glassmorphism** | Semi-transparent cards with `backdrop-filter: blur()` |
| **Animated Orbs** | Floating gradient blurred circles for ambient glow |
| **Micro-Animations** | fadeInUp, pulse-dot, counter animations, hover effects |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Landing  │  │ Request Help │  │ Volunteer│  │   Admin    │  │
│  │   Page    │  │    Form      │  │Dashboard │  │ Analytics  │  │
│  └──────────┘  └──────┬───────┘  └────┬─────┘  └────────────┘  │
│                       │               │                         │
│         GPS + Nominatim Geocoding     │  Socket.IO + Leaflet    │
└───────────────────────┼───────────────┼─────────────────────────┘
                        │               │
                   POST /request_help   │  GET /volunteer
                        │               │
┌───────────────────────▼───────────────▼─────────────────────────┐
│                      FLASK SERVER (app.py)                       │
│                                                                  │
│  ┌─────────────────┐    ┌──────────────────────────────────┐    │
│  │  Route Handlers  │    │  Helper Functions                │    │
│  │  - request_help  │    │  - calculate_distance (Haversine)│    │
│  │  - volunteer     │    │  - find_nearby_requests          │    │
│  │  - admin/analytics│   │  - notify_nearby_volunteers      │    │
│  │  - login/register│    │  - validate_required_fields      │    │
│  └────────┬─────────┘    └──────────────────────────────────┘    │
│           │                                                      │
│  ┌────────▼─────────┐                                           │
│  │   ai_engine.py   │◄──── NVIDIA NIM API (LLM Triage)         │
│  │  predict_emergency│     meta/llama-3.2-3b-instruct           │
│  └──────────────────┘                                           │
└──────────┬──────────────────────┬───────────────────┬───────────┘
           │                      │                   │
    ┌──────▼──────┐       ┌──────▼──────┐     ┌──────▼──────┐
    │  DynamoDB   │       │  DynamoDB   │     │   AWS SNS   │
    │ Volunteers  │       │  Requests   │     │  SMS Alerts  │
    │   Table     │       │   Table     │     │             │
    └─────────────┘       └─────────────┘     └─────────────┘
```

---

## 📁 Project Structure

```
HelpHive/
│
├── app.py                      # Flask application — routes, logic, AWS integration
├── ai_engine.py                # AI emergency triage engine (NVIDIA NIM)
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not committed)
├── .gitignore                  # Git exclusions
├── README.md                   # This file
│
├── templates/                  # Jinja2 HTML templates
│   ├── index.html              # Landing page (self-contained CSS/JS)
│   ├── request_help.html       # Emergency request form
│   ├── volunteer_login.html    # Login & registration portal
│   ├── volunteer.html          # Volunteer dashboard
│   └── admin_analytics.html    # Admin analytics dashboard
│
└── static/
    ├── css/
    │   ├── volunteer.css       # Volunteer dashboard styles
    │   └── admin_analytics.css # Admin dashboard styles
    └── js/
        └── volunteer.js        # Dashboard logic (charts, map, Socket.IO)
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- AWS account with DynamoDB and SNS access
- NVIDIA NIM API key ([get one here](https://build.nvidia.com/))

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/gagandeepgn94-code/Help_Hive.git
cd Help_Hive

# 2. Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file (see Environment Variables section below)

# 5. Run the application
python app.py
```

The app will be available at **(https://help-hive-y9rs.onrender.com)**

---

## 🔑 Environment Variables

Create a `.env` file in the project root with the following:

```env
# Flask
SECRET_KEY=your-secret-key-here

# AWS Credentials
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=ap-south-1

# NVIDIA NIM AI Engine
NVIDIA_API_KEY=your-nvidia-api-key
NVIDIA_MODEL=meta/llama-3.2-3b-instruct
```

### AWS Setup

1. **DynamoDB Tables** — Create two tables:
   - `Volunteers` (Partition Key: `volunteer_id`, String)
   - `Requests` (Partition Key: `request_id`, String)

2. **Global Secondary Indexes (GSIs)**:
   - `name-index` on Volunteers table (Partition Key: `name`)
   - `category-index` on Volunteers table (Partition Key: `category`)
   - `category-status-index` on Requests table (Partition Key: `category`)

3. **SNS** — Ensure your AWS account has SMS sending permissions

---

## 🛣️ API Routes

### Public

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Landing page |
| `GET` | `/request-help` | Emergency request form |
| `POST` | `/request_help` | Submit request → AI triage → SMS |
| `GET` | `/volunteer_login` | Login / Register page |
| `POST` | `/login_volunteer` | Authenticate volunteer |
| `POST` | `/register_volunteer` | Create volunteer account |
| `GET` | `/admin/analytics` | Global analytics dashboard |

### Protected (requires login)

| Method | Route | Description |
|---|---|---|
| `GET` | `/volunteer` | Volunteer dashboard |
| `GET` | `/accept/<id>` | Accept a request |
| `GET` | `/complete/<id>` | Mark request completed |
| `GET` | `/delete/<id>` | Delete a request |
| `GET` | `/logout` | End session |

---

## 🧠 AI Engine

The AI engine (`ai_engine.py`) uses the **NVIDIA NIM Chat Completions API** with `meta/llama-3.2-3b-instruct` to analyze emergency requests in real-time.

### What it does

For every emergency request, the AI returns:

| Field | Example | Description |
|---|---|---|
| `priority` | `Critical` | AI-assessed priority (Critical / High / Medium / Low) |
| `severity_score` | `9.8` | Severity on a 1.0–10.0 scale |
| `confidence` | `0.90` | Model confidence (0.0–1.0) |
| `recommended_radius` | `20` | Optimal volunteer search radius in KM |
| `notify_immediately` | `true` | Whether to send SMS immediately |
| `reason` | `"Unconscious person not breathing"` | Clinical justification |

### Fault Tolerance

- ✅ Every API error returns a safe fallback — **Flask never crashes**
- ✅ JSON parsing uses **4 strategies** (direct, code-fence strip, brace extraction, unescape)
- ✅ All values validated and clamped to safe ranges
- ✅ Detailed logging at every step for debugging

> **Important:** The user's selected priority is **never overwritten**. Both `priority` (user) and `ai_priority` (AI) are stored separately.

---

## 🗄️ Database Schema

### Volunteers Table

| Field | Type | Description |
|---|---|---|
| `volunteer_id` | String (PK) | UUID |
| `name` | String | Full name (GSI: `name-index`) |
| `password` | String | bcrypt hash |
| `phone` | String | Phone number for SMS |
| `category` | String | Specialty (GSI: `category-index`) |
| `availability` | String | "Available" / "Busy" |
| `latitude` / `longitude` | String | GPS coordinates |

### Requests Table

| Field | Type | Description |
|---|---|---|
| `request_id` | String (PK) | UUID |
| `name` | String | Requester name |
| `category` | String | Emergency type |
| `help` | String | Description |
| `priority` | String | **User-selected** priority |
| `status` | String | Pending / Accepted / Completed |
| `ai_priority` | String | **AI-predicted** priority |
| `ai_severity_score` | String | AI severity (1.0–10.0) |
| `ai_confidence` | String | AI confidence (0.0–1.0) |
| `ai_recommended_radius` | String | AI search radius in KM |
| `ai_notify_immediately` | Boolean | Immediate SMS flag |
| `ai_reason` | String | AI clinical justification |

---

## 🖥️ Pages & Screenshots

| Page | Route | Description |
|---|---|---|
| **Landing Page** | `/` | Hero section, stats, how-it-works, services, CTA |
| **Request Help** | `/request-help` | Emergency form with GPS auto-detection |
| **Volunteer Login** | `/volunteer_login` | Split-panel login & registration |
| **Volunteer Dashboard** | `/volunteer` | Stat cards, charts, live map, request cards with AI insights |
| **Admin Analytics** | `/admin/analytics` | Global metrics, 3 charts, recent requests table |

---

## 👥 Contributors

| Name | Role |
|---|---|
| **Gagandeep** | Full-Stack Developer |
| **Sachin Goudar** | UI/UX Engineer |
| **Kiran Kumar K S** | Frontend Developer |

---

## 📄 License

This project was built as part of the **PBL 2nd Semester** curriculum at **GM University**.

---

<p align="center">
  <strong>Help<span>Hive</span></strong> — Connecting Communities. Saving Lives. 🐝
</p>
