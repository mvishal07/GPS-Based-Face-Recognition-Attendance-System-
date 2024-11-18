from flask import Flask, request, jsonify, flash
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import base64
import cv2
import numpy as np
import face_recognition
import mysql.connector
import csv
from io import StringIO
from flask import make_response

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flashing messages
CORS(app)  # Enable CORS

# Predefined college location (latitude, longitude)
COLLEGE_LOCATION = (17.461684933237464, 78.48025238711105) #17.461684933237464, 78.48025238711105

def is_within_location(current_location, target_location, threshold=0.02):
    current_lat, current_lon = current_location
    target_lat, target_lon = target_location
    return abs(current_lat - target_lat) < threshold and abs(current_lon - target_lon) < threshold

def register_student(student_id, name, image_data,password):
    # Decode the image data
    image_data = base64.b64decode(image_data.split(',')[1])
    nparr = np.frombuffer(image_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vishal@1662",
        database="attendance_systems"
    )
    cursor = conn.cursor()

    # Check if a face is detected
    face_encodings = face_recognition.face_encodings(frame)
    if len(face_encodings) > 0:
        face_encoding = face_encodings[0]

        # Insert student data into the database
        cursor.execute("INSERT INTO students (student_id, name, face_image,password) VALUES (%s, %s, %s,%s)", 
                       (student_id, name, image_data,password))
        conn.commit()
        return {"message": f"Student {name} registered successfully."}
    else:
        return {"message": "Error: No face detected. Please try again."}
    

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data['username']
    password = data['password']

    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vishal@1662",
        database="attendance_systems"
    )
    cursor = conn.cursor()

    cursor.execute("SELECT password FROM admin WHERE username = %s", (username,))
    result = cursor.fetchone()

    if result and check_password_hash(result[0], password):
        # Admin login successful
        return jsonify({"message": "Admin logged in successfully."})
    else:
        return jsonify({"message": "Invalid username or password."}), 401
@app.route('/admin/register', methods=['POST'])
def admin_register():
    data = request.json
    username = data['username']
    password = generate_password_hash(data['password'])

    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vishal@1662",
        database="attendance_systems"
    )
    cursor = conn.cursor()

    cursor.execute("INSERT INTO admin (username, password) VALUES (%s, %s)", (username, password))
    conn.commit()

    return jsonify({"message": "Admin registered successfully."})

@app.route('/student/login', methods=['POST'])
def student_login():
    data = request.json
    student_id = data['student_id']
    password = data['password']

    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vishal@1662",
        database="attendance_systems"
    )
    cursor = conn.cursor()

    cursor.execute("SELECT password FROM students WHERE student_id = %s", (student_id,))
    result = cursor.fetchone()

    if result and check_password_hash(result[0], password):
        # Student login successful
        return jsonify({"message": "Student logged in successfully."})
    else:
        return jsonify({"message": "Invalid student ID or password."}), 401


def mark_attendance(student_id, latitude, longitude):
    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vishal@1662",
        database="attendance_systems"
    )
    cursor = conn.cursor()

    # Current location from the user
    current_location = (latitude, longitude)

    # Retrieve the student's face encoding from the database
    cursor.execute("SELECT face_image FROM students WHERE student_id = %s", (student_id,))
    result = cursor.fetchone()
    
    if not result:
        return {"message": "Student not found."}

    # Decode the image from the database
    np_arr = np.frombuffer(result[0], np.uint8)
    db_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    db_face_encoding = face_recognition.face_encodings(db_image)[0]

    # Capture live image from the webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return {"message": "Error: Could not open webcam."}

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return {"message": "Error: Failed to capture image."}

    live_face_encodings = face_recognition.face_encodings(frame)
    if len(live_face_encodings) > 0:
        live_face_encoding = live_face_encodings[0]

        # Compare the face encodings
        matches = face_recognition.compare_faces([db_face_encoding], live_face_encoding)
        
        if matches[0]:
            if is_within_location(current_location, COLLEGE_LOCATION):
                # Mark attendance
                location_str = f"{latitude},{longitude}"
                cursor.execute("INSERT INTO attendance (student_id, attendance_date, attendance_time, timestamp, location) VALUES (%s, CURDATE(), CURTIME(), NOW(), %s)", 
                               (student_id, location_str))
                conn.commit()
                return {"message": "Attendance marked successfully."}
            else:
                return {"message": "Error: You are not within the college location."}
        else:
            return {"message": "Error: Face did not match."}
    else:
        return {"message": "Error: No face detected. Please try again."}

@app.route('/register', methods=['POST'])
def register():
    # Check if the admin is logged in before registering a new student
    data = request.json
    student_id = data['student_id']
    name = data['name']
    image_data = data['image_data']
    password = generate_password_hash(data['password'])  # Store the student's password

    result = register_student(student_id, name, image_data, password)
    return jsonify(result)


@app.route('/attendance', methods=['POST'])
def attendance():
    data = request.json
    student_id = data['student_id']
    latitude = data['latitude']
    longitude = data['longitude']
    result = mark_attendance(student_id, latitude, longitude)
    return jsonify(result)


@app.route('/admin/download_attendance', methods=['GET'])
def download_attendance():
    # Connect to MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Vishal@1662",
        database="attendance_systems"
    )
    cursor = conn.cursor()

    # Query attendance records
    cursor.execute("SELECT student_id, attendance_date, attendance_time, location FROM attendance")
    attendance_records = cursor.fetchall()

    # Create a CSV file in-memory
    output = StringIO()
    writer = csv.writer(output)

    # Write the header
    writer.writerow(['Student ID', 'Attendance Date', 'Attendance Time', 'Location'])

    # Write the attendance records
    for row in attendance_records:
        writer.writerow(row)

    # Prepare the response to be downloadable as a CSV file
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=attendance_records.csv"
    response.headers["Content-type"] = "text/csv"

    return response


if __name__ == '__main__':
    app.run(debug=True)
