import json
import sqlite3
import os
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE = 'database.db'

# --- Database Functions ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Drop tables to ensure a clean slate on each initialization
        cursor.execute("DROP TABLE IF EXISTS users")
        cursor.execute("DROP TABLE IF EXISTS competitions")
        cursor.execute("DROP TABLE IF EXISTS competitors")
        cursor.execute("DROP TABLE IF EXISTS competition_competitors")

        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                password TEXT PRIMARY KEY,
                role TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competitions (
                name TEXT PRIMARY KEY,
                date TEXT,
                location TEXT,
                description TEXT,
                status TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competitors (
                id TEXT PRIMARY KEY,
                name TEXT,
                nationality TEXT,
                status TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competition_competitors (
                competition_name TEXT,
                competitor_id TEXT,
                FOREIGN KEY (competition_name) REFERENCES competitions(name),
                FOREIGN KEY (competitor_id) REFERENCES competitors(id),
                PRIMARY KEY (competition_name, competitor_id)
            )
        ''')
        db.commit()

        # Load initial data from JSON files if they exist, otherwise use default data
        if load_initial_data():
            print("Initial data loaded from JSON files.")
        else:
            print("JSON files not found. Loading default data.")
            load_default_data()

def load_initial_data():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        try:
            # Check if all files exist before attempting to load
            if not os.path.exists('users.json') or \
               not os.path.exists('competitions.json') or \
               not os.path.exists('competitors.json'):
                return False

            # Load users
            with open('users.json', 'r') as f:
                users_data = json.load(f)
                for password, details in users_data.items():
                    cursor.execute("INSERT OR IGNORE INTO users (password, role) VALUES (?, ?)", 
                                   (password, details['role']))

            # Load competitions
            with open('competitions.json', 'r') as f:
                competitions_data = json.load(f)
                for name, details in competitions_data.items():
                    cursor.execute("INSERT OR IGNORE INTO competitions (name, date, location, description, status) VALUES (?, ?, ?, ?, ?)", 
                                   (details['name'], details['date'], details['location'], details['description'], details['status']))
                    if 'competitor_ids' in details:
                        for comp_id in details['competitor_ids']:
                            cursor.execute("INSERT OR IGNORE INTO competition_competitors (competition_name, competitor_id) VALUES (?, ?)", 
                                           (details['name'], comp_id))
            
            # Load competitors
            with open('competitors.json', 'r') as f:
                competitors_data = json.load(f)
                for comp_id, details in competitors_data.items():
                    cursor.execute("INSERT OR IGNORE INTO competitors (id, name, nationality, status) VALUES (?, ?, ?, ?)", 
                                   (details['id'], details['name'], details['nationality'], details['status']))

            db.commit()
            return True
        except FileNotFoundError as e:
            print(f"Error loading initial data: {e}. Please ensure you have the correct JSON files.")
            return False
        except Exception as e:
            print(f"An error occurred during data loading: {e}")
            return False

def load_default_data():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Add a default admin user
        cursor.execute("INSERT OR IGNORE INTO users (password, role) VALUES (?, ?)", ('admin', 'admin'))

        # Add some sample competitions
        competitions = [
            ('Winter Grand Prix', 'March 1, 2025', 'London, UK', 'The inaugural Winter Grand Prix in the heart of London.', 'Completed'),
            ('Spring Cup Championship', 'May 15, 2025', 'Paris, France', 'An exciting championship for upcoming talents.', 'Upcoming'),
            ('Summer Open', 'July 20, 2025', 'Tokyo, Japan', 'The biggest event of the year.', 'Upcoming')
        ]
        cursor.executemany("INSERT OR IGNORE INTO competitions (name, date, location, description, status) VALUES (?, ?, ?, ?, ?)", competitions)
        
        # Add some sample competitors
        competitors = [
            ('COMP-001', 'Alex Smith', 'American', 'Active'),
            ('COMP-002', 'Maria Garcia', 'Spanish', 'Active'),
            ('COMP-003', 'Kenji Tanaka', 'Japanese', 'Active')
        ]
        cursor.executemany("INSERT OR IGNORE INTO competitors (id, name, nationality, status) VALUES (?, ?, ?, ?)", competitors)
        
        # Link some competitors to competitions
        competition_competitors = [
            ('Winter Grand Prix', 'COMP-001'),
            ('Winter Grand Prix', 'COMP-002'),
            ('Spring Cup Championship', 'COMP-001'),
            ('Summer Open', 'COMP-003')
        ]
        cursor.executemany("INSERT OR IGNORE INTO competition_competitors (competition_name, competitor_id) VALUES (?, ?)", competition_competitors)

        db.commit()
        print("Default data loaded successfully.")

# --- User Management API Endpoints ---
@app.route('/api/login', methods=['POST'])
def login():
    password = request.json.get('password')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT role FROM users WHERE password = ?", (password,))
    user = cursor.fetchone()
    if user:
        return jsonify(success=True, message="Login successful.", role=user['role'])
    else:
        return jsonify(success=False, message="Invalid password.")

@app.route('/api/signup', methods=['POST'])
def signup():
    password = request.json.get('password')
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (password, role) VALUES (?, 'general')", (password,))
        db.commit()
        return jsonify(success=True, message="User created successfully. You can now log in.")
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="User already exists.")

@app.route('/api/users', methods=['GET'])
def get_users():
    db = get_db()
    users = db.execute("SELECT password, role FROM users").fetchall()
    return jsonify([dict(u) for u in users])

@app.route('/api/users/add', methods=['POST'])
def add_user():
    password = request.json.get('password')
    role = request.json.get('role', 'general')
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (password, role) VALUES (?, ?)", (password, role))
        db.commit()
        return jsonify(success=True, message="User added successfully.")
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="User already exists.")

@app.route('/api/users/remove', methods=['POST'])
def remove_user():
    password = request.json.get('password')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE password = ?", (password,))
    db.commit()
    return jsonify(success=True, message="User removed successfully.")

# --- Competition Management API Endpoints ---
@app.route('/api/competitions', methods=['GET'])
def get_competitions():
    db = get_db()
    competitions = db.execute("SELECT * FROM competitions").fetchall()
    return jsonify([dict(c) for c in competitions])

@app.route('/api/competitions/add', methods=['POST'])
def add_competition():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO competitions (name, date, location, description, status) VALUES (?, ?, ?, ?, ?)", 
                       (data['name'], data['date'], data['location'], data['description'], "Upcoming"))
        db.commit()
        return jsonify(success=True, message="Competition added successfully.")
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="Competition with this name already exists.")

@app.route('/api/competitions/remove', methods=['POST'])
def remove_competition():
    name = request.json.get('name')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM competitions WHERE name = ?", (name,))
    db.commit()
    return jsonify(success=True, message="Competition removed successfully.")
    
@app.route('/api/competitions/edit', methods=['POST'])
def edit_competition():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE competitions SET name = ?, date = ?, location = ?, description = ?, status = ? WHERE name = ?",
                       (data['new_name'], data['new_date'], data['new_location'], data['new_description'], data['new_status'], data['original_name']))
        db.commit()
        return jsonify(success=True, message="Competition updated successfully.")
    except Exception as e:
        return jsonify(success=False, message=str(e))

@app.route('/api/competitions/<competition_name>/competitors', methods=['GET'])
def get_competition_competitors(competition_name):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        SELECT c.name, c.nationality
        FROM competitors c
        JOIN competition_competitors cc ON c.id = cc.competitor_id
        WHERE cc.competition_name = ?
    ''', (competition_name,))
    competitors = cursor.fetchall()
    return jsonify([dict(comp) for comp in competitors])

@app.route('/api/competitions/add_competitor', methods=['POST'])
def add_competitor_to_competition():
    data = request.json
    competition_name = data.get('competition_name')
    competitor_id = data.get('competitor_id')
    
    if not competition_name or not competitor_id:
        return jsonify(success=False, message="Competition name and competitor ID are required.")
    
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO competition_competitors (competition_name, competitor_id) VALUES (?, ?)", (competition_name, competitor_id))
        db.commit()
        return jsonify(success=True, message="Competitor assigned successfully.")
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="Competitor is already assigned to this competition.")
    except Exception as e:
        return jsonify(success=False, message=f"An error occurred: {e}")

# --- Competitor Management API Endpoints ---
@app.route('/api/competitors', methods=['GET'])
def get_competitors():
    db = get_db()
    competitors = db.execute("SELECT * FROM competitors").fetchall()
    return jsonify([dict(c) for c in competitors])
    
@app.route('/api/competitors/<competitor_id>/profile', methods=['GET'])
def get_competitor_profile(competitor_id):
    db = get_db()
    cursor = db.cursor()
    
    # Get competitor details
    cursor.execute("SELECT * FROM competitors WHERE id = ?", (competitor_id,))
    competitor = cursor.fetchone()
    
    if not competitor:
        return jsonify(success=False, message="Competitor not found."), 404
        
    competitor_details = dict(competitor)

    # Get competitions the competitor participated in
    cursor.execute('''
        SELECT c.name, c.date, c.location
        FROM competitions c
        JOIN competition_competitors cc ON c.name = cc.competition_name
        WHERE cc.competitor_id = ?
    ''', (competitor_id,))
    competitions = cursor.fetchall()
    
    competitor_details['competitions'] = [dict(comp) for comp in competitions]
    
    return jsonify(competitor_details)

@app.route('/api/competitors/add', methods=['POST'])
def add_competitor():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO competitors (id, name, nationality, status) VALUES (?, ?, ?, ?)", 
                       (data['id'], data['name'], data['nationality'], data['status']))
        db.commit()
        return jsonify(success=True, message="Competitor added successfully.")
    except sqlite3.IntegrityError:
        return jsonify(success=False, message="Competitor with this ID already exists.")

@app.route('/api/competitors/remove', methods=['POST'])
def remove_competitor():
    comp_id = request.json.get('id')
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM competitors WHERE id = ?", (comp_id,))
    db.commit()
    return jsonify(success=True, message="Competitor removed successfully.")

@app.route('/api/competitors/edit', methods=['POST'])
def edit_competitor():
    data = request.json
    db = get_db()
    cursor = db.cursor()
    try:
        # Update competitor in the competitors table
        cursor.execute("UPDATE competitors SET name = ?, id = ?, nationality = ?, status = ? WHERE id = ?",
                       (data['new_name'], data['new_id'], data['new_nationality'], data['new_status'], data['original_id']))
        # Update competitor ID in the competition_competitors table as well
        cursor.execute("UPDATE competition_competitors SET competitor_id = ? WHERE competitor_id = ?",
                       (data['new_id'], data['original_id']))
        db.commit()
        return jsonify(success=True, message="Competitor updated successfully.")
    except Exception as e:
        return jsonify(success=False, message=str(e))

if __name__ == '__main__':
    # Initialize the database on the first run.
    init_db()
    app.run(debug=True)