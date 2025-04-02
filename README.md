# EMAG-Fitness1 Dashboard

The EMAG-Fitness1 Dashboard is a web application designed to integrate and synchronize product data between the EMAG marketplace and the Fitness1 system. The application provides a user-friendly dashboard for managing product data, category mappings, and scheduling automatic update processes.

## Table of Contents

- [EMAG-Fitness1 Dashboard](#emag-fitness1-dashboard)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Technologies Used](#technologies-used)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Setup Instructions](#setup-instructions)
  - [Configuration](#configuration)
  - [Database Migrations](#database-migrations)
  - [Running the Application](#running-the-application)
  - [API Endpoints](#api-endpoints)
    - [Product Endpoints](#product-endpoints)
    - [Mapping Endpoints](#mapping-endpoints)
    - [Scheduling Endpoints](#scheduling-endpoints)
  - [Dashboard Overview](#dashboard-overview)
  - [Testing](#testing)
  - [Deployment](#deployment)
    - [Production Checklist](#production-checklist)
  - [Contributing](#contributing)
  - [License](#license)
  - [Contact](#contact)

## Features

- **Product Management:**
  Retrieve and display product data from EMAG and Fitness1.

- **Category Mappings:**
  Manage category mappings between Fitness1 and EMAG. Create, update, and delete mappings with persistent storage using SQLite and SQLAlchemy.

- **Scheduled Updates:**
  Schedule automatic updates of product data using APScheduler with options for time-based (cron) or interval-based scheduling. Jobs persist across application restarts.

- **Responsive Dashboard UI:**
  A modern, responsive dashboard built with Bootstrap 5, featuring separate tabs for Operations, Products, Mappings, and Scheduling.

- **RESTful API Endpoints:**
  Exposes API endpoints for product retrieval, mapping management, and scheduling control.

- **Database Migrations:**
  Managed via Flask-Migrate for smooth schema evolution.

## Technologies Used

- Python 3.x
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-APScheduler / APScheduler
- Bootstrap 5
- SQLite

## Installation

### Prerequisites

- Python 3.x installed
- Virtual environment tool (e.g., `venv` or `virtualenv`)

### Setup Instructions

1. **Clone the Repository:**

```bash
git clone https://github.com/yourusername/idcars-emag.git
cd idcars-emag
```


2. **Create and Activate a Virtual Environment:**


```bash
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

4. **Install Dependencies:**


```bash
pip install -r requirements.txt
```


## Configuration

Create a `.env` file in the project root to set your environment variables. For example:


```env
SECRET_KEY=your_secret_key_here
EMAG_API_KEY=your_emag_api_key_here
FITNESS1_API_KEY=your_fitness1_api_key_here
DATABASE_URL=sqlite:///app.db
FLASK_ENV=development
```

The `config.py` file loads these variables and sets up your configuration:


```python
import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    EMAG_API_KEY = os.environ.get("EMAG_API_KEY")
    FITNESS1_API_KEY = os.environ.get("FITNESS1_API_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SCHEDULER_API_ENABLED = True
    APSCHEDULER_JOBSTORES = {
        "default": {"type": "sqlalchemy", "url": SQLALCHEMY_DATABASE_URI}
    }
    APSCHEDULER_JOB_DEFAULTS = {"coalesce": False, "max_instances": 1}
    APSCHEDULER_TIMEZONE = os.environ.get("APScheduler_TIMEZONE", "Europe/Sofia")
```


## Database Migrations


We use Flask-Migrate to handle database schema changes.


2. **Initialize the Migrations Directory:**


```bash
flask db init
```

4. **Generate a Migration Script:**


```bash
flask db migrate -m "Initial migration"
```

6. **Apply the Migration:**


```bash
flask db upgrade
```

8. **Populate Allowed Categories:**
Run the provided initialization script to populate the `FitnessCategory` table:


```bash
python initialize.py
```


## Running the Application


2. **Start the Flask Application:**


```bash
flask run
```


For production, you might use Gunicorn:



```bash
gunicorn -w 4 run:app
```

4. **Access the Dashboard:**
Open your browser and navigate to `http://127.0.0.1:5000`.


## API Endpoints


### Product Endpoints


- **
GET `/api/products/fitness1`**

Retrieves all Fitness1 products.

- **
GET `/api/products/emag`**

Retrieves all EMAG products.


### Mapping Endpoints


- **
GET `/api/mappings`**

Retrieves current category mappings.

- **
POST `/api/mappings`**

Creates a new mapping.

- **
PATCH `/api/mappings`**

Bulk updates mappings.

- **
GET `/api/categories`**

Retrieves allowed EMAG categories from the database.


### Scheduling Endpoints


- **
POST `/scheduler/schedule`**

Schedules an update job (either time-based or interval-based).

- **
GET `/scheduler/job`**

Retrieves details about the scheduled update job.

- **
DELETE `/scheduler/cancel`**

Cancels the scheduled update job.

- **
POST `/scheduler/trigger`**

Manually triggers the update job.


## Dashboard Overview


The dashboard provides several tabs:


- **Operations:**

Trigger product creation/update manually and view real-time logs.

- **Products:**

View products from Fitness1 and EMAG in responsive, scrollable tables.

- **Mappings:**

Manage category mappings with inline editing (EMAG category as a dropdown).

- **Scheduling:**

Schedule automatic update processes with options for time-based or interval-based scheduling.


## Testing


To run automated tests (if you have tests set up):



```bash
pytest
```


Ensure you configure a testing database if necessary.


## Deployment


### Production Checklist


- **Environment Variables:**

Set `FLASK_ENV=production` and use a secure `SECRET_KEY`.

- **WSGI Server:**

Deploy using Gunicorn or uWSGI for production.


```bash
gunicorn -w 4 run:app
```

- **Containerization:**

Consider using Docker for consistent deployment across environments.

- **Migrations:**

Run `flask db upgrade` during deployment to ensure the schema is up-to-date.

- **Logging:**

Configure logging to capture errors and operational messages.


## Contributing


Contributions are welcome! Please fork the repository, create a new branch, and submit a pull request with your changes. Ensure that your code adheres to the project's style and includes tests where applicable.


## License

This project is licensed under the [MIT License]() .

## Contact

For questions, issues, or further information, please open an issue on GitHub or contact [Your Name] at [[your.email@example.com]() ].
