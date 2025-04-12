from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, session, flash
from pymongo import MongoClient
import qrcode
from io import BytesIO
from bson.objectid import ObjectId
import os
from werkzeug.utils import secure_filename
import base64
import secrets
 
 
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = secrets.token_hex(16)  # For session management
 
 # MongoDB connection
client = MongoClient('mongodb+srv://divya:16feb1976@care.k5vvsif.mongodb.net/?authSource=admin')
db = client['students']
users_collection = db['data']
fs = db['fs']  # For GridFS
 
 # Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
     os.makedirs(app.config['UPLOAD_FOLDER'])
 
@app.route('/')
def index():
     return render_template('form.html')
 
@app.route('/view')
def view():
     return render_template('view.html')
 
@app.route('/book')
def book():
     return render_template('getQR.html')
@app.route('/order_qr',methods=['POST'])
def order_QR():
     order=db["orderdata"]
     fname=request.form.get("name")
     lname=request.form.get("regd_no")
     email=request.form.get("email")
     addr1=request.form.get("Address_Line_1")
     phone=request.form.get("phone")
     add2=request.form.get("Address_Line_2")
     city=request.form.get("City")
     State=request.form.get("State")
     pin=request.form.get("Pincode")
     gender=request.form.get("gender")
     emergency=request.form.get("emergency_contact")
     order.insert_one({'fname':fname,
                       'lname':lname,
                       'email':email,
                       'addr1':addr1,
                       'phone':phone,
                       "add2":add2,
                       "city":city,
                       "state":State,
                       "pin":pin,
                       "gender":gender,
                       "emergency":emergency,
                       })
     return render_template("Razorpay.html")
 
 
 
 
 
@app.route('/login', methods=['GET', 'POST'])
def login():
     if request.method == 'POST':
         regd_no = request.form.get('regd_no')
         contact = request.form.get('contact')
         
         user = users_collection.find_one({'regd_no': regd_no})
         if not user or user['contact'] != contact:
             return "Invalid credentials", 401
         
         # Direct access without QR authentication
         return redirect(f'/patient/{regd_no}')
     
     return render_template('login.html')
 
@app.route('/post', methods=['POST'])
def post():
     try:
         data = request.form.to_dict()
         files = request.files.getlist('prescriptions')
         
         if not files:
             return "No prescription images uploaded.", 400
 
         # Save prescription images
         image_filenames = []
         for file in files:
             if file:
                 filename = f"{data['regd_no']}_{secure_filename(file.filename)}"
                 file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                 file.save(file_path)
                 image_filenames.append(filename)
 
         # Generate QR code with login URL
         qr = qrcode.QRCode(version=1, box_size=10, border=5)
         qr.add_data(f"http://localhost:3019/qr_login")
         qr.make(fit=True)
         qr_image = qr.make_image(fill_color="black", back_color="white")
         
         # Save QR code
         qr_filename = f"{data['regd_no']}_qr.png"
         qr_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_filename)
         qr_image.save(qr_path)
        
         
         # Save to MongoDB
         user_data = {
             'regd_no': data['regd_no'],
             'name': data['name'],
             'email': data['email'],
             'dob': data['dob'],
             'gender': data['gender'],
             'contact': data['contact'],
             'address': data['address'],
             'emergency_contact': data['emergency_contact'],
             'allergies': data['allergies'],
             'medications': data['medications'],
             'chronic': data['chronic'],
             'symptoms': data['symptoms'],
             'prescription_images': image_filenames,
             'qr_code': qr_filename
         }
         
         users_collection.insert_one(user_data)
         return render_template('success.html',user=user_data)
 
     except Exception as e:
         print(f"Error: {e}")
         return "An error occurred while processing your request.", 500
 
@app.route('/qr_login', methods=['GET', 'POST'])
def qr_login():
     if request.method == 'POST':
         regd_no = request.form.get('regd_no')
         contact = request.form.get('contact')
         
         user = users_collection.find_one({'regd_no': regd_no})
         if not user or user['contact'] != contact:
             flash('Invalid credentials. Please try again.', 'error')
             return render_template('qr_login.html')
         
         session['qr_authenticated'] = True
         session['qr_regd_no'] = regd_no
         return redirect(f'/patient/{regd_no}')
     
     return render_template('qr_login.html')
 
@app.route('/patient/<regd_no>')
def patient(regd_no):
     # Check if the request is coming from QR code scan
     if request.referrer and 'qr_login' in request.referrer:
         if not session.get('qr_authenticated') or session.get('qr_regd_no') != regd_no:
             return redirect('/qr_login')
     
     user = users_collection.find_one({'regd_no': regd_no})
     if not user:
         return "Patient not found.", 404
     
     return render_template('patient.html', user=user)
 
@app.route('/logout')
def logout():
     session.pop('qr_authenticated', None)
     session.pop('qr_regd_no', None)
     return redirect('/qr_login')
 
@app.route('/image/<filename>')
def serve_image(filename):
     return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
 
@app.route('/qr/<regd_no>')
def serve_qr(regd_no):
     user = users_collection.find_one({'regd_no': regd_no})
     if not user or 'qr_code' not in user:
         return "QR code not found.", 404
     
     return send_file(os.path.join(app.config['UPLOAD_FOLDER'], user['qr_code']))
 
@app.route('/print')
def printqr():
     return render_template("qrprint.html")
 
@app.route('/submit',methods=['POST'])
def submitqr():
     user=request.form.get("regd_no")
     mobile=request.form.get("contact")
     person=users_collection.find_one({'regd_no': user})
     return render_template("final.html",user=person)
 
@app.route('/edit/<regd_no>', methods=['GET'])
def edit(regd_no):
     user = users_collection.find_one({"regd_no": regd_no})
     if not user:
         return "Patient not found.", 404
 
     return render_template('edit.html', user=user)
 
@app.route('/update/<regd_no>', methods=['POST'])
def update(regd_no):
     user = users_collection.find_one({"regd_no": regd_no})
     if not user:
         return "Patient not found.", 404
 
     name = request.form.get("name")
     email = request.form.get("email")
     dob = request.form.get("dob")
     gender = request.form.get("gender")
     contact = request.form.get("contact")
     address = request.form.get("address")
     emergency_contact = request.form.get("emergency_contact")
     allergies = request.form.get("allergies")
     medications = request.form.get("medications")
     chronic = request.form.get("chronic")
     symptoms = request.form.get("symptoms")
     files = request.files.getlist("prescriptions")
 
     imageFilenames = user.get("prescription_images", [])
 
     if files and len(files) > 0:
         imageFilenames = []
         for file in files:
             if file:
                 filename = f"{regd_no}_{secure_filename(file.filename)}"
                 file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                 file.save(file_path)
                 imageFilenames.append(filename)
 
     # Update user data in MongoDB
     users_collection.update_one({"regd_no": regd_no}, {"$set": {
         "name": name,
         "email": email,
         "dob": dob,
         "gender": gender,
         "contact": contact,
         "address": address,
         "emergency_contact": emergency_contact,
         "allergies": allergies,
         "medications": medications,
         "chronic": chronic,
         "symptoms": symptoms,
         "prescription_images": imageFilenames
     }})
 
     # Regenerate QR code
     qr_data = f"http://localhost:3019/qr_login"
     qr_image = qrcode.make(qr_data)
     qr_filename = f"{regd_no}_qr.png"
     qr_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_filename)
     qr_image.save(qr_path)
 
     users_collection.update_one({"regd_no": regd_no}, {"$set": {
         "qr_code": qr_filename
     }})
 
     return redirect(f"/patient/{regd_no}")
# @app.route('/add_prescription/<regd_no>', methods=['GET', 'POST'])
# def add_prescription(regd_no):
#     user = users_collection.find_one({"regd_no": regd_no})
#     if not user:
#         return "Patient not found.", 404

#     if request.method == 'POST':
#         files = request.files.getlist('prescriptions')
#         notes = request.form.get("doctor_notes", "")

#         imageFilenames = user.get("prescription_images", [])
#         doctorNotes = user.get("doctor_notes", "")

#         for file in files:
#             if file:
#                 filename = f"{regd_no}_{secure_filename(file.filename)}"
#                 file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#                 file.save(file_path)
#                 imageFilenames.append(filename)

#         # Append new notes to existing ones (optional: add timestamp)
#         if notes:
#             doctorNotes += f"\n\n---\n{notes}"

#         users_collection.update_one({"regd_no": regd_no}, {
#             "$set": {
#                 "prescription_images": imageFilenames,
#                 "doctor_notes": doctorNotes
#             }
#         })

#         return redirect(f"/patient/{regd_no}")

#     return render_template('add_prescription.html', user=user)
 
if __name__ == '__main__':
     app.run(port=3019, debug=True)
