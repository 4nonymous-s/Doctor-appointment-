# Hospital Appointment Finder - Mini Project

This project contains:

- Flask backend (`app.py`), SQLAlchemy models (`models.py`).
- SQLite init script (`init_db.sql`) with seed data.
- A simple fallback HTML UI (`templates/index.html`) and a React app scaffold in `react_app/`.

## Quick start

1. Create virtual env and install packages:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
```

2. Initialize database:
```bash
sqlite3 hospital.db < init_db.sql
```

3. Run Flask:
```bash
python app.py
```

4. (Optional) To run the React app locally:
```bash
cd react_app
npm install
npm start
```

The Flask backend serves APIs under `/api/*`.
