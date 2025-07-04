# Getting Started

## Prerequisites
- Python 3.12+
- MongoDB instance (currently using mongo v3.4)
- (Optional) Docker & Docker Compose

## Installation
```bash
git clone --branch dev https://github.com/SMD-Bioinformatics-Lund/coyote3.git
cd coyote3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration
Copy .env.example or edit config.py to set: MONGODB_URI SECRET_KEY  Authentication (LDAP/OAuth) variables

## Run Locally
```bash
python run.py
``` 

## Production Mode
```bash
gunicorn --timeout 240 -w 2 --threads 2 -e SCRIPT_NAME="" --log-level INFO --bind 0.0.0.0:8000 wsgi:app
```

## Docker (optional) via shell script
```
bash scripts/install.sh
```

## Docker Compose (optional)
```bash
docker-compose up --build
```