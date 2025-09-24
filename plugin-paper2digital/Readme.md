# Paper2Digital

**Paper2Digital** is a Moodle-integrated project designed to convert paper-based content into a digital format. It consists of a **backend API server** and a **Moodle plugin** (frontend) that communicates with it. The system also includes a chatbot for interactive queries and digital assistance.

---

## Table of Contents
1. [Tech Stack](#tech-stack)  
2. [Folder Structure](#folder-structure)  
3. [Prerequisites](#prerequisites)  
4. [Backend Setup](#backend-setup)  
5. [Plugin Setup](#plugin-setup)  
6. [Running the System](#running-the-system)  
7. [API Endpoints](#api-endpoints)  
8. [Database Integration](#database-integration)  
9. [Testing](#testing)  
10. [Troubleshooting](#troubleshooting)  

---

## Tech Stack
- **Python 3.10+** – Backend server  
- **Flask** – Web framework  
- **Snowflake** – Database  
- **PHP** – Moodle plugin  
- **REST APIs** – Communication between plugin and backend  
- **Moodle 4.x** – Learning management system  

---

## Folder Structure
```
paper2digital/
│
├── backend/                 # Backend server
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   ├── routes/
│   ├── services/
│   └── utils/
│
├── plugin/                  # Moodle plugin
│   ├── version.php
│   ├── lang/
│   ├── classes/
│   ├── db/
│   └── index.php
│
└── README.md                # This file
```

---

## Prerequisites
1. **Python 3.10+**  
2. **Virtual Environment** (`venv`)  
3. **Moodle 4.x** installed locally or on server  
4. **Snowflake account** with database, schema, and warehouse  
5. **Composer** (optional, for PHP dependency management)  

---

## Backend Setup

1. Navigate to the backend folder:
```bash
cd paper2digital/backend
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Configure environment variables in `.env` or `config.py`:
```ini
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=public
```

6. Run the backend server:
```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
```
The API is accessible at: `http://localhost:5000`

---

## Plugin Setup

1. Copy the plugin folder into Moodle’s local plugin directory:
```text
moodle/local/plugin/   # or moodle/local/paper2digital/
```

2. Login to Moodle as admin and navigate to:
```
Site Administration → Plugins → Install plugins
```

3. Moodle will detect the new plugin. Click **Install** and follow the on-screen instructions.

4. Configure the plugin with the backend URL:
```text
http://localhost:5000
```

---

## Running the System
1. Start the backend server (Flask).  
2. Start Moodle (local or server).  
3. Access the Moodle plugin through the admin or course interface.  
4. Interact with the chatbot or digital content; the plugin communicates with the backend API.

---

## API Endpoints
Backend API endpoints are prefixed with `/api`:

| Method | Endpoint          | Description                            |
|--------|-------------------|----------------------------------------|
| GET    | /api/health       | Checks backend health                  |
| POST   | /api/query        | Accepts queries and fetches data       |
| GET    | /api/data/table   | Fetch data from specified table        |
| POST   | /api/chat         | Chatbot interaction endpoint           |

---

## Database Integration
Snowflake is used for storing and retrieving digital content. Connection is handled via `backend/services/snowflake_service.py`.

Example:
```python
from services.snowflake_service import SnowflakeService

sf = SnowflakeService()
data = sf.execute_query("SELECT * FROM my_table LIMIT 10")
print(data)
```

---

## Testing
- Test backend endpoints using **Postman** or **cURL**:
```bash
curl -X GET http://localhost:5000/api/health
```

- Test the plugin through the Moodle interface.

---

## Troubleshooting
- **Backend connection errors:** Check Snowflake credentials, network access, and environment variables.  
- **Flask server not starting:** Ensure the virtual environment is active and `FLASK_APP` is set.  
- **Moodle plugin not showing:** Verify folder structure and correct placement in Moodle’s local plugins directory.

