# FoodBridge – Smart Restaurant Food Waste Management

Flask + SQLite + vanilla JS (Leaflet/OpenStreetMap, Chart.js). Needs Python 3.9+ and internet access (map tiles/CDN libraries).

## Run locally
```bash
cd foodbridge
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                                        # open http://127.0.0.1:5000
```
The database (`foodbridge.db`) and ~180 days of demo data are created on first run. Delete the file to reset.

## Demo accounts
| Role | Email | Password |
|---|---|---|
| Admin | admin@foodbridge.test | admin123 |
| Restaurant | green@demo.test (also spice@, urban@, coastal@, bread@, curry@) | demo123 |
| NGO | annapurna@demo.test (also hope@, seva@, care@) | demo123 |

## Structure
```
app.py            Flask API, auth, validation, seed data, forecast/recommendation logic
templates/        index.html (single-page shell)
static/           app.js (views, API calls, map, charts), style.css
Dockerfile        cloud-ready container (gunicorn)
```

## AI/ML – honest status
`/api/ml` is a **demo statistical forecast** (weekday averages x 14-day trend) from the donation table; `/api/recommend` is a **rule-based score** (proximity + NGO workload). Neither is a trained or validated ML model, and the UI labels them as demos. To go further, train a model (e.g. scikit-learn) on real history and swap it in at those endpoints.
Waste/CO₂ figures use stated assumptions (0.4 kg/serving, 2.5 kg CO₂e/kg) — adjust in `app.py`.

## Cloud / MySQL
Set `SECRET_KEY` and `DB_PATH` env vars; deploy with `docker build` or `gunicorn app:app`. To use MySQL, replace the `sqlite3` calls in `db()/q()/ex()/init()` with PyMySQL (the SQL is standard apart from `INTEGER PRIMARY KEY` → `AUTO_INCREMENT` and `substr` → `SUBSTRING`).
