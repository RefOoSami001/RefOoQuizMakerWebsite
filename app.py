from flask import Flask, render_template, request, jsonify
import requests
import PyPDF2
import io
import sqlite3
import os
import random
import string
import json
from datetime import datetime

app = Flask(__name__)

# Database setup
DATABASE = 'quizzes.db'

def init_db():
    if not os.path.exists(DATABASE):
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE quizzes (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

init_db()

def save_quiz_to_db(quiz_id, quiz_data):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO quizzes (id, data) VALUES (?, ?)', (quiz_id, quiz_data))
    conn.commit()
    conn.close()

def get_quiz_from_db(quiz_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT data FROM quizzes WHERE id = ?', (quiz_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def generate_simple_id():
    """Generate a simple, user-friendly quiz ID."""
    # Get the current timestamp (e.g., 20231025 for October 25, 2023)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    # Generate a random 4-character string (letters and digits)
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    # Combine the timestamp and random part
    return f"{timestamp}-{random_part}"

def get_questions(topic, num_questions, lang):
    cookies = {
        'AMP_MKTG_70a5be3710': 'JTdCJTdE',
        'AMP_70a5be3710': 'JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjJhMzA0ODk0OS05MWIwLTQ1OTMtYjU5MC04OTQ1NThiOWFiMTIlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzM0ODAxMjg3NDc0JTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJsYXN0RXZlbnRUaW1lJTIyJTNBMTczNDgwMTI4NzQ3OSUyQyUyMmxhc3RFdmVudElkJTIyJTNBMiU3RA==',
        '__client_uat': '0',
        '__client_uat_wYOPO35R': '0',
        'crisp-client%2Fsession%2Ffaab0820-f408-4327-915b-bc17f2332d39': 'session_92021fc7-4cf5-4b64-b5fe-82d6f3e1874c',
        '__stripe_mid': '0d785786-3f51-48e0-aa0a-cdb754b7a83a4809ce',
        '__stripe_sid': '9454cd36-334d-4ee8-a53e-faa4e76a9b170c32eb',
    }

    headers = {
        'accept': '*/*',
        'accept-language': 'ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7',
        'baggage': 'sentry-environment=vercel-production,sentry-release=69b2b1c3f422dff6472132d59e8581489aa8427a,sentry-public_key=f6bbb7b197a2a7e09bc25634f533bdeb,sentry-trace_id=8d0baca7f0634408bfce0e8857294d98',
        'content-type': 'application/json',
        'origin': 'https://www.heuristi.ca',
        'priority': 'u=1, i',
        'referer': 'https://www.heuristi.ca/tools/free-ai-quiz-generator',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'sentry-trace': '8d0baca7f0634408bfce0e8857294d98-8ca3ef1a40dafdf7',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    json_data = {
        'operation': 'quiz-from-text',
        'input': topic,
        'language': lang,
        'count': str(num_questions),
    }

    response = requests.post('https://www.heuristi.ca/api/free-flashcard-generator', cookies=cookies, headers=headers, json=json_data)
    return response.json()

def extract_text_from_pdf(pdf_file, start_page, end_page):
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page_num in range(start_page - 1, end_page):
        page = reader.pages[page_num]
        text += page.extract_text()
    return text

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate-flashcards', methods=['POST'])
def generate_flashcards():
    if request.method == 'POST':
        # Get form data
        num_questions = int(request.form['num_questions'])
        language = request.form['language']

        # Determine if the user provided text or a PDF
        if 'topicText' in request.form and request.form['topicText'].strip():
            # Use text input
            text = request.form['topicText'].strip()
        else:
            # Use PDF input
            if 'pdf_file' not in request.files:
                return jsonify({'error': 'No PDF file uploaded'}), 400
            pdf_file = request.files['pdf_file']
            if pdf_file.filename == '':
                return jsonify({'error': 'No PDF file selected'}), 400

            # Get page range
            try:
                start_page = int(request.form['start_page'])
                end_page = int(request.form['end_page'])
            except (KeyError, ValueError):
                return jsonify({'error': 'Invalid page range'}), 400

            # Extract text from the selected pages
            text = extract_text_from_pdf(pdf_file, start_page, end_page)

        # Get questions from the API
        questions = get_questions(text, num_questions, language)

        # Generate a simple quiz ID
        quiz_id = generate_simple_id()

        # Save the quiz to the database
        save_quiz_to_db(quiz_id, json.dumps(questions['data']))

        # Return the quiz ID and shareable link
        shareable_link = f"{request.host_url}quiz/{quiz_id}"
        return jsonify({'questions': questions['data'], 'shareable_link': shareable_link})

@app.route('/quiz/<quiz_id>')
def view_quiz(quiz_id):
    # Get the quiz data from the database
    quiz_data = get_quiz_from_db(quiz_id)
    if not quiz_data:
        return "Quiz not found", 404

    # Render the quiz page
    return render_template('flashcards.html', questions=json.loads(quiz_data))

if __name__ == '__main__':
    app.run(debug=True)
