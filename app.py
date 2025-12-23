# app.py
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import csv
import shutil
import traceback
from pathlib import Path
from functools import lru_cache
import argparse
import random

CACHE_DIR = Path('.')
DB_FILE = 'hospital.db'  # legacy path (no longer used for storage)
app = Flask(__name__, static_folder='react_app/build', template_folder='templates')
CORS(app)
app.secret_key = os.environ.get('APP_SECRET', 'dev-secret-key')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'dev-admin-token')

# CSV data sources (authoritative)
HOSPITALS_CSV = Path('hospital_directory.csv')
DOCTORS_CSV = Path('doctors.csv')
DOCTORS_SHUFFLED = Path('doctors_shuffled.csv')
USERS_CSV = Path('users.csv')
APPTS_CSV = Path('appointments.csv')


# CSV loaders with simple caching
@lru_cache(maxsize=1)
def load_hospitals_csv():
    if not HOSPITALS_CSV.exists():
        return []
    with HOSPITALS_CSV.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    # Normalize keys for easier access
    cleaned = []
    for r in rows:
        # pick sensible fields if available
        hosp_id = r.get('Sr_No') or r.get('SrNo') or r.get('id')
        name = r.get('Hospital_Name') or r.get('Hospital_Name'.lower()) or r.get('HospitalName') or r.get('Hospital') or r.get('Hospital_Name')
        locality = r.get('Town') or r.get('Location') or r.get('Subdistrict') or r.get('District') or ''
        address = r.get('Address_Original_First_Line') or r.get('Address') or r.get('Address_Original') or ''
        cleaned.append({'id': int(hosp_id) if hosp_id and str(hosp_id).isdigit() else hosp_id, 'name': name, 'locality': locality, 'address': address, 'raw': r})
    return cleaned


@lru_cache(maxsize=1)
def load_doctors_csv():
    # prefer persisted shuffled file if present
    source = DOCTORS_SHUFFLED if DOCTORS_SHUFFLED.exists() else DOCTORS_CSV
    if not source.exists():
        return []
    with source.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    cleaned = []
    for r in rows:
        # keep types conservative; many fields may be strings
        try:
            doc_id = int(r.get('id')) if r.get('id') else None
        except Exception:
            doc_id = r.get('id')
        try:
            hosp_id = int(r.get('hospital_id')) if r.get('hospital_id') else None
        except Exception:
            hosp_id = r.get('hospital_id')
        cleaned.append({
            'id': doc_id,
            'hospital_id': hosp_id,
            'name': r.get('name'),
            'specialty': r.get('specialty'),
            'is_available': True if str(r.get('is_available')).strip() in ('1','True','true','t','yes') else False,
            'ward': None,
            'qualification': r.get('qualification'),
            'experience_years': int(r.get('experience_years')) if r.get('experience_years') and str(r.get('experience_years')).isdigit() else (None if not r.get('experience_years') else r.get('experience_years')),
            'email': r.get('email'),
            'phone': r.get('phone')
        })
    return cleaned


def ensure_min_doctors(hospital_id, doctors_list, target=10):
    """Return a list with at least `target` doctors for the given hospital_id.
    If there are fewer than `target` doctors in `doctors_list`, generate
    deterministic placeholder doctors (in-memory only) and return the combined list.
    """
    if len(doctors_list) >= target:
        return doctors_list

    # Compute a starting id that won't collide with existing integer ids
    all_docs = load_doctors_csv()
    existing_ids = [d.get('id') for d in all_docs if isinstance(d.get('id'), int)]
    max_id = max(existing_ids) if existing_ids else 0
    next_id = max_id + 1

    # small name lists for deterministic realistic generation
    FIRST_NAMES = ['Priya','Amit','Suman','Neha','Karan','Pooja','Vikram','Anita','Ritu','Siddharth','Isha','Rahul','Meera','Kavita','Ramesh']
    LAST_NAMES = ['Sharma','Singh','Patel','Iyer','Nair','Bose','Kumar','Verma','Reddy','Desai','Kapoor','Das','Menon','Chopra','Gupta']
    specialties = ['General', 'Cardiology', 'ENT', 'Orthopedics', 'Dermatology', 'Pediatrics', 'Gynecology', 'Neurology']
    qualifications = ['MBBS', 'MD', 'DNB', 'MS', 'DM']

    generated = []
    i = 0
    while len(doctors_list) + len(generated) < target:
        idx = i + 1
        # deterministic seed per hospital and index
        seed = (hash(str(hospital_id)) & 0xffffffff) + idx
        rnd = random.Random(seed)
        fn = rnd.choice(FIRST_NAMES)
        ln = rnd.choice(LAST_NAMES)
        name = f"Dr. {fn} {ln}"
        specialty = specialties[(seed) % len(specialties)]
        qualification = qualifications[(seed) % len(qualifications)]
        experience = (seed % 30) + 1
        email = f"{fn.lower()}.{ln.lower()}{next_id}@example.com"
        phone = f"90000{(next_id % 100000):05d}"
        gen = {
            'id': next_id,
            'hospital_id': hospital_id,
            'name': name,
            'specialty': specialty,
            'is_available': True,
            'ward': None,
            'qualification': qualification,
            'experience_years': experience,
            'email': email,
            'phone': phone,
        }
        generated.append(gen)
        next_id += 1
        i += 1

    return doctors_list + generated

# -----------------------
# CSV-backed users & appointments
# -----------------------

def ensure_csv(path: Path, headers):
    if not path.exists():
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)


def load_users():
    if not USERS_CSV.exists():
        return []
    with USERS_CSV.open(newline='', encoding='utf-8') as f:
        first = f.readline()
        f.seek(0)
        # if file has header (contains 'username' or 'id'), use DictReader
        if 'username' in first.lower() or 'id' in first.lower():
            reader = csv.DictReader(f)
            users = list(reader)
        else:
            # no header - fall back to positional columns: id,username,password_hash,full_name,phone
            reader = csv.reader(f)
            users = []
            for row in reader:
                if not row:
                    continue
                # pad row
                while len(row) < 5:
                    row.append('')
                users.append({'id': row[0], 'username': row[1], 'password_hash': row[2], 'full_name': row[3], 'phone': row[4]})
    # normalize ids
    for u in users:
        try:
            u['id'] = int(u.get('id')) if u.get('id') and str(u.get('id')).isdigit() else u.get('id')
        except Exception:
            pass
    return users


def find_user_by_username(username):
    users = load_users()
    for u in users:
        if u.get('username') == username:
            return u
    return None


def create_user(username, password_hash, full_name='', phone=''):
    users = load_users()
    # compute next numeric id safely (ignore non-numeric ids)
    numeric_ids = [int(u.get('id')) for u in users if u.get('id') and str(u.get('id')).isdigit()]
    next_id = (max(numeric_ids) + 1) if numeric_ids else 1
    row = {'id': next_id, 'username': username, 'password_hash': password_hash, 'full_name': full_name, 'phone': phone}
    # ensure header exists
    ensure_csv(USERS_CSV, ['id', 'username', 'password_hash', 'full_name', 'phone'])
    with USERS_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([row['id'], row['username'], row['password_hash'], row['full_name'], row['phone']])
    return row


def load_appointments():
    if not APPTS_CSV.exists():
        return []
    with APPTS_CSV.open(newline='', encoding='utf-8') as f:
        first = f.readline()
        f.seek(0)
        if 'user_id' in first.lower() or 'id' in first.lower():
            reader = csv.DictReader(f)
            appts = list(reader)
        else:
            reader = csv.reader(f)
            appts = []
            for row in reader:
                if not row:
                    continue
                while len(row) < 7:
                    row.append('')
                appts.append({'id': row[0], 'user_id': row[1], 'doctor_id': row[2], 'hospital_id': row[3], 'scheduled_at': row[4], 'status': row[5], 'created_at': row[6]})
    for a in appts:
        try:
            a['id'] = int(a.get('id')) if a.get('id') and str(a.get('id')).isdigit() else a.get('id')
        except Exception:
            pass
        try:
            a['user_id'] = int(a.get('user_id')) if a.get('user_id') and str(a.get('user_id')).isdigit() else a.get('user_id')
        except Exception:
            pass
        try:
            a['doctor_id'] = int(a.get('doctor_id')) if a.get('doctor_id') and str(a.get('doctor_id')).isdigit() else a.get('doctor_id')
        except Exception:
            pass
        try:
            a['hospital_id'] = int(a.get('hospital_id')) if a.get('hospital_id') and str(a.get('hospital_id')).isdigit() else a.get('hospital_id')
        except Exception:
            pass
    return appts


def append_appointment(user_id, doctor_id, hospital_id, scheduled_at_iso, status='booked'):
    appts = load_appointments()
    # compute next numeric id safely (ignore non-numeric ids)
    numeric_ids = [int(a.get('id')) for a in appts if a.get('id') and str(a.get('id')).isdigit()]
    next_id = (max(numeric_ids) + 1) if numeric_ids else 1
    created_at = datetime.utcnow().isoformat()
    row = {'id': next_id, 'user_id': user_id, 'doctor_id': doctor_id, 'hospital_id': hospital_id, 'scheduled_at': scheduled_at_iso, 'status': status, 'created_at': created_at}
    # ensure header exists
    ensure_csv(APPTS_CSV, ['id', 'user_id', 'doctor_id', 'hospital_id', 'scheduled_at', 'status', 'created_at'])
    with APPTS_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([row['id'], row['user_id'], row['doctor_id'], row['hospital_id'], row['scheduled_at'], row['status'], row['created_at']])
    return row

# Routes
@app.route('/')
def index():
    # if React build exists, serve it. Otherwise fallback to simple HTML.
    if os.path.exists(os.path.join(app.static_folder, 'index.html')):
        return send_from_directory(app.static_folder, 'index.html')
    return render_template('index.html')


# User dashboard page (per-user)
@app.route('/dashboard')
def user_dashboard():
    # Expect a user_id query parameter (client sets this after login)
    user_id = request.args.get('user_id')
    if not user_id:
        return redirect(url_for('index'))
    try:
        user_id_n = int(user_id) if str(user_id).isdigit() else user_id
    except Exception:
        user_id_n = user_id
    # find user
    user = None
    for u in load_users():
        if u.get('id') == user_id_n or str(u.get('id')) == str(user_id_n):
            user = u
            break
    if not user:
        return redirect(url_for('index'))

    # load user's appointments
    appts = load_appointments()
    user_appts = [a for a in appts if str(a.get('user_id')) == str(user_id_n)]
    # augment appointments with doctor/hospital friendly fields
    doctors = load_doctors_csv()
    hospitals = load_hospitals_csv()
    enriched = []
    for a in sorted(user_appts, key=lambda x: x.get('created_at') or '', reverse=True):
        did = a.get('doctor_id')
        hid = a.get('hospital_id')
        doc = next((d for d in doctors if d.get('id') == did or str(d.get('id')) == str(did)), None)
        hosp = next((h for h in hospitals if h.get('id') == hid or str(h.get('id')) == str(hid)), None)
        enriched.append({
            'id': a.get('id'),
            'doctor': doc.get('name') if doc else None,
            'hospital': hosp.get('name') if hosp else None,
            'scheduled_at': a.get('scheduled_at'),
            'status': a.get('status'),
            'created_at': a.get('created_at')
        })

    return render_template('user_dashboard.html', user=user, appointments=enriched)


# Serve our legacy static folder (templates reference /static/style.css). The app's
# static folder is configured for the React build; expose the local `static/` dir
# so the fallback UI can load CSS and assets.
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# User registration
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name', '')
    phone = data.get('phone', '')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    if find_user_by_username(username):
        return jsonify({'error': 'username already exists'}), 400
    password_hash = generate_password_hash(password)
    create_user(username, password_hash, full_name=full_name, phone=phone)
    return jsonify({'message': 'registered successfully'})

# User login (simple token: return user id; in production use JWT or sessions)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    user = find_user_by_username(username)
    if not user or not check_password_hash(user.get('password_hash', ''), password):
        return jsonify({'error': 'invalid credentials'}), 401
    return jsonify({'message': 'ok', 'user_id': user.get('id'), 'username': user.get('username')})

# Search hospitals by locality
@app.route('/api/hospitals', methods=['GET'])
def hospitals():
    locality = request.args.get('locality', '').strip()
    # Prefer CSV-backed hospitals if present
    if HOSPITALS_CSV.exists():
        hospitals = load_hospitals_csv()
        if locality:
            locality_l = locality.lower()
            hospitals = [h for h in hospitals if (h.get('locality') or '').lower().find(locality_l) != -1 or (h.get('name') or '').lower().find(locality_l) != -1]
        # Return id, name, locality, address
        out = [{'id': h.get('id'), 'name': h.get('name'), 'locality': h.get('locality'), 'address': h.get('address')} for h in hospitals]
        return jsonify(out)

    # If CSV is missing, return empty list (no sqlite fallback)
    return jsonify([])

# Get wards and doctors for a hospital
@app.route('/api/hospital/<int:hospital_id>/doctors', methods=['GET'])
def hospital_doctors(hospital_id):
    # Prefer CSV-backed doctors if present
    if DOCTORS_CSV.exists():
        doctors = load_doctors_csv()
        matched = [d for d in doctors if d.get('hospital_id') == hospital_id or str(d.get('hospital_id')) == str(hospital_id)]
        # ensure at least 10 doctors are returned (generate placeholders if needed)
        matched = ensure_min_doctors(hospital_id, matched, target=10)
        out = []
        for d in matched:
            out.append({
                'id': d.get('id'),
                'name': d.get('name'),
                'specialty': d.get('specialty'),
                'is_available': bool(d.get('is_available')),
                'ward': d.get('ward'),
                'qualification': d.get('qualification'),
                'experience_years': d.get('experience_years'),
                'email': d.get('email'),
                'phone': d.get('phone'),
            })
        return jsonify(out)

    # If CSV missing return empty list (no sqlite fallback)
    return jsonify([])

# Check doctor availability and existing bookings (simple)
@app.route('/api/doctor/<int:doctor_id>/availability', methods=['GET'])
def doctor_availability(doctor_id):
    doctors = load_doctors_csv()
    doc = None
    for d in doctors:
        if d.get('id') == doctor_id or str(d.get('id')) == str(doctor_id):
            doc = d
            break
    if not doc:
        return jsonify({'error': 'doctor not found'}), 404
    appts = load_appointments()
    upcoming = sum(1 for a in appts if (a.get('doctor_id') == doctor_id or str(a.get('doctor_id')) == str(doctor_id)) and a.get('status') == 'booked')
    return jsonify({'doctor_id': doctor_id, 'is_available': bool(doc.get('is_available')), 'booked_count': upcoming})

# Book appointment
@app.route('/api/book', methods=['POST'])
def book():
    try:
        data = request.get_json() or {}
        # Booking payload no longer requires user_id or doctor_id.
        # Expect at minimum: hospital_id and scheduled_at (ISO string).
        hospital_id = data.get('hospital_id')
        scheduled_at = data.get('scheduled_at')  # ISO string
        if not hospital_id or not scheduled_at:
            return jsonify({'error': 'hospital_id and scheduled_at required'}), 400
        # validate hospital exists (CSV)
        hospitals = load_hospitals_csv()
        hosp = None
        for h in hospitals:
            if h.get('id') == hospital_id or str(h.get('id')) == str(hospital_id):
                hosp = h
                break
        if not hosp:
            return jsonify({'error': 'hospital not found'}), 404
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_at) if scheduled_at else None
        except Exception:
            return jsonify({'error': 'invalid scheduled_at format, use ISO format'}), 400
        # If no user_id provided, use/ensure a guest user in CSV users
        user_id = data.get('user_id')
        if not user_id:
            guest = find_user_by_username('guest')
            if not guest:
                guest = create_user('guest', generate_password_hash('guest'), full_name='Guest User')
            user_id = guest.get('id')
        # Ensure a doctor_id is set so existing DB NOT NULL constraints are satisfied.
        # Prefer any existing doctor for the hospital; if none exists, create a guest-doctor tied to the hospital.
        doctor_id = data.get('doctor_id')
        if not doctor_id:
            # Try to pick an existing doctor for this hospital from CSV
            doctors = load_doctors_csv()
            doc = None
            for d in doctors:
                if d.get('hospital_id') == hospital_id or str(d.get('hospital_id')) == str(hospital_id):
                    doc = d
                    break
            if not doc:
                # try find guest-doctor for hospital
                for d in doctors:
                    if d.get('hospital_id') == hospital_id and d.get('name') == 'guest-doctor':
                        doc = d
                        break
            if not doc:
                # append a guest-doctor to doctors.csv
                # determine fieldnames from existing file or use defaults
                default_fields = ['id','hospital_id','name','specialty','is_available','ward_id','qualification','experience_years','email','phone']
                if DOCTORS_CSV.exists():
                    with DOCTORS_CSV.open(newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        fieldnames = reader.fieldnames or default_fields
                else:
                    fieldnames = default_fields
                # find next id
                existing = load_doctors_csv()
                # compute next numeric id safely (ignore non-numeric ids)
                numeric_ids = [int(d.get('id')) for d in existing if d.get('id') and str(d.get('id')).isdigit()]
                next_id = (max(numeric_ids) + 1) if numeric_ids else 1
                guest_row = {k: '' for k in fieldnames}
                guest_row['id'] = next_id
                guest_row['hospital_id'] = hospital_id
                guest_row['name'] = 'guest-doctor'
                guest_row['specialty'] = 'N/A'
                guest_row['is_available'] = '0'
                # append to file
                with DOCTORS_CSV.open('a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([guest_row.get(fn, '') for fn in fieldnames])
                # reload doctors
                doc = None
                for d in load_doctors_csv():
                    if d.get('id') == next_id:
                        doc = d
                        break
            doctor_id = doc.get('id')
        # Create appointment in CSV
        appt_row = append_appointment(user_id, doctor_id, hospital_id, scheduled_dt.isoformat() if scheduled_dt else '', status='booked')
        return jsonify({'message': 'appointment booked', 'appointment_id': appt_row.get('id')})
    except Exception as e:
        # Log traceback to server console and return JSON error so clients can parse it
        traceback.print_exc()
        return jsonify({'error': 'internal server error', 'detail': str(e)}), 500

# Booking history for a user
@app.route('/api/history/<int:user_id>', methods=['GET'])
def history(user_id):
    appts = load_appointments()
    filtered = [a for a in appts if a.get('user_id') == user_id or str(a.get('user_id')) == str(user_id)]
    # sort by created_at desc
    filtered.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    doctors = load_doctors_csv()
    hospitals = load_hospitals_csv()
    out = []
    for a in filtered:
        did = a.get('doctor_id')
        hid = a.get('hospital_id')
        doc = next((d for d in doctors if d.get('id') == did or str(d.get('id')) == str(did)), None)
        hosp = next((h for h in hospitals if h.get('id') == hid or str(h.get('id')) == str(hid)), None)
        out.append({'id': a.get('id'), 'doctor': doc.get('name') if doc else None, 'hospital': hosp.get('name') if hosp else None, 'scheduled_at': a.get('scheduled_at'), 'status': a.get('status'), 'created_at': a.get('created_at')})
    return jsonify(out)


def save_appointments(appts_list):
    """Persist appointments list back to CSV. Overwrites `appointments.csv`.
    `appts_list` is a list of dicts with keys matching the header.
    """
    hdr = ['id', 'user_id', 'doctor_id', 'hospital_id', 'scheduled_at', 'status', 'created_at']
    # Create an automatic timestamped backup before overwriting the appointments CSV
    try:
        if APPTS_CSV.exists():
            ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            # e.g. appointments.bak.20251119T153000Z.csv
            backup_name = f"{APPTS_CSV.stem}.bak.{ts}{APPTS_CSV.suffix}"
            backup_path = APPTS_CSV.with_name(backup_name)
            shutil.copy2(APPTS_CSV, backup_path)
    except Exception as e:
        # If backup fails, log and continue to attempt to save (do not silently drop changes)
        print(f"Warning: failed to create appointments backup: {e}")

    with APPTS_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(hdr)
        for a in appts_list:
            writer.writerow([
                a.get('id', ''),
                a.get('user_id', ''),
                a.get('doctor_id', ''),
                a.get('hospital_id', ''),
                a.get('scheduled_at', ''),
                a.get('status', ''),
                a.get('created_at', ''),
            ])


@app.route('/api/appointment/<int:appt_id>/cancel', methods=['POST'])
def cancel_appointment(appt_id):
    """Mark an appointment as cancelled. Request body should include `user_id` to verify ownership,
    or supply a valid admin token in `X-Admin-Token` header or `admin_token` cookie.
    """
    data = request.get_json() or {}
    requester_user_id = data.get('user_id')
    token = request.headers.get('X-Admin-Token') or request.cookies.get('admin_token')

    appts = load_appointments()
    target = None
    for a in appts:
        if a.get('id') == appt_id or str(a.get('id')) == str(appt_id):
            target = a
            break
    if not target:
        return jsonify({'error': 'appointment not found'}), 404

    # Allow cancellation if requester is owner or a valid admin token is provided
    owner_ok = requester_user_id and str(target.get('user_id')) == str(requester_user_id)
    admin_ok = token and ADMIN_TOKEN and str(token) == str(ADMIN_TOKEN)
    if not (owner_ok or admin_ok):
        return jsonify({'error': 'unauthorized'}), 401

    target['status'] = 'cancelled'
    save_appointments(appts)
    return jsonify({'ok': True, 'appointment_id': target.get('id'), 'status': target.get('status')})


# Clear booking history for a user (owner or admin)
@app.route('/api/history/<int:user_id>/clear', methods=['POST'])
def clear_user_history(user_id):
    data = request.get_json() or {}
    requester_user_id = data.get('user_id')
    token = request.headers.get('X-Admin-Token') or request.cookies.get('admin_token')

    appts = load_appointments()
    # verify permission: either owner (requester_user_id matches user_id) or admin token
    owner_ok = requester_user_id and str(requester_user_id) == str(user_id)
    admin_ok = token and ADMIN_TOKEN and str(token) == str(ADMIN_TOKEN)
    if not (owner_ok or admin_ok):
        return jsonify({'error': 'unauthorized'}), 401

    # Remove appointments for the user (keep others). We treat this as deletion.
    remaining = [a for a in appts if not (str(a.get('user_id')) == str(user_id))]
    save_appointments(remaining)
    return jsonify({'ok': True, 'removed_for_user': user_id, 'remaining_count': len(remaining)})


# Admin-only: clear all booking history
@app.route('/api/history/clear_all', methods=['POST'])
def clear_all_history():
    token = request.headers.get('X-Admin-Token') or request.cookies.get('admin_token')
    if not (token and ADMIN_TOKEN and str(token) == str(ADMIN_TOKEN)):
        return jsonify({'error': 'unauthorized'}), 401
    # wipe appointments file (keep header)
    save_appointments([])
    return jsonify({'ok': True, 'remaining_count': 0})

if __name__ == '__main__':
    # Ensure CSV backing files exist with headers
    ensure_csv(USERS_CSV, ['id', 'username', 'password_hash', 'full_name', 'phone'])
    ensure_csv(APPTS_CSV, ['id', 'user_id', 'doctor_id', 'hospital_id', 'scheduled_at', 'status', 'created_at'])
    # doctors.csv and hospital_directory.csv are expected to be provided by the project
    if not HOSPITALS_CSV.exists():
        print('Warning: hospital_directory.csv not found. /api/hospitals will return empty results until it is provided.')
    if DOCTORS_SHUFFLED.exists():
        print('Found doctors_shuffled.csv; app will prefer it for /api/hospital/<id>/doctors')
    elif not DOCTORS_CSV.exists():
        print('Warning: doctors.csv not found. /api/hospital/<id>/doctors will return empty results until it is provided.')
    app.run(debug=True)
