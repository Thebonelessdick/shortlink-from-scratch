from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps  # Tambahkan import ini untuk memperbaiki error
import random
import string
import os
import logging
from database import init_db, save_url, get_url, increment_clicks, get_clicks, verify_user, get_user_urls, update_url, delete_url

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-fallback")

gunicorn_logger = logging.getLogger('gunicorn.error')
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)

try:
    init_db()
    app.logger.info("Database initialized successfully")
except Exception as e:
    app.logger.error(f"Error during database initialization: {e}")

def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Dekorator login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if verify_user(username, password):
            session['username'] = username
            session.permanent = True
            app.logger.info(f"User {username} logged in successfully")
            return redirect(url_for('home'))
        app.logger.warning(f"Failed login attempt for username: {username}")
        return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    session.pop('username', None)
    app.logger.info(f"User {username} logged out")
    return redirect(url_for('login'))

@app.route('/')
def landing():
    return render_template('landing.html', base_url=request.url_root)

@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    username = session['username']
    page = 1
    per_page = 5
    urls, total_urls = get_user_urls(username, page, per_page)

    if request.method == 'POST':
        try:
            original_url = request.form['url']
            custom_code = request.form.get('custom_code', '').strip()

            if not original_url.startswith(('http://', 'https://')):
                original_url = 'http://' + original_url
                
            if not original_url:
                return render_template('index.html', error="Please enter a URL", urls=urls, base_url=request.url_root)

            if custom_code:
                if not custom_code.isalnum():
                    return render_template('index.html', error="Custom code can only contain letters and numbers", urls=urls, base_url=request.url_root)
                if len(custom_code) > 20:
                    return render_template('index.html', error="Custom code must be 20 characters or less", urls=urls, base_url=request.url_root)
                if get_url(custom_code):
                    return render_template('index.html', error="Custom code already in use, please choose another", urls=urls, base_url=request.url_root)
                short_code = custom_code
            else:
                short_code = generate_short_code()
                while get_url(short_code):
                    short_code = generate_short_code()
            
            save_url(short_code, original_url, username)
            short_url = f"{request.url_root}{short_code}"
            app.logger.info(f"Short URL created: {short_url}")
            return render_template('index.html', short_url=short_url, urls=urls, base_url=request.url_root)
        except Exception as e:
            app.logger.error(f"Error in home route: {e}")
            return render_template('index.html', error="An error occurred", urls=urls, base_url=request.url_root)
    
    return render_template('index.html', urls=urls, base_url=request.url_root)

@app.route('/dashboard')
@login_required
def dashboard():
    username = session['username']
    # Ambil nomor halaman dari query parameter, default ke 1
    page = int(request.args.get('page', 1))
    per_page = 10  # Jumlah data per halaman

    # Ambil data URL dan total jumlah URL
    urls, total_urls = get_user_urls(username, page, per_page)

    # Hitung total halaman
    total_pages = (total_urls + per_page - 1) // per_page

    return render_template(
        'dashboard.html',
        urls=urls,
        base_url=request.url_root,
        page=page,
        total_pages=total_pages
    )

@app.route('/edit/<short_code>', methods=['GET', 'POST'])
@login_required
def edit_url(short_code):
    if request.method == 'POST':
        try:
            new_original_url = request.form['original_url']
            new_short_code = request.form['short_code'].strip()

            if not new_original_url.startswith(('http://', 'https://')):
                new_original_url = 'http://' + new_original_url

            if not new_original_url:
                return jsonify({'success': False, 'error': 'Please enter a URL'}), 400

            if not new_short_code.isalnum():
                return jsonify({'success': False, 'error': 'Short code can only contain letters and numbers'}), 400

            if len(new_short_code) > 20:
                return jsonify({'success': False, 'error': 'Short code must be 20 characters or less'}), 400

            success = update_url(short_code, new_original_url, new_short_code)
            if not success:
                return jsonify({'success': False, 'error': 'New short code already in use, please choose another'}), 400

            app.logger.info(f"Short URL {short_code} updated to {new_short_code} by {session['username']}")
            return jsonify({'success': True})
        except Exception as e:
            app.logger.error(f"Error in edit_url: {e}")
            return jsonify({'success': False, 'error': 'An error occurred'}), 500

    # Untuk GET request (opsional, jika masih ingin mendukung akses langsung ke edit.html)
    original_url = get_url(short_code)
    if not original_url:
        return redirect(url_for('dashboard'))
    return render_template('edit.html', short_code=short_code, original_url=original_url)

@app.route('/delete/<short_code>')
@login_required
def delete_url_route(short_code):
    try:
        delete_url(short_code)
        app.logger.info(f"Short URL {short_code} deleted by {session['username']}")
        return redirect(url_for('dashboard'))
    except Exception as e:
        app.logger.error(f"Error in delete_url: {e}")
        return redirect(url_for('dashboard'))

@app.route('/<short_code>')
def redirect_to_url(short_code):
    try:
        original_url = get_url(short_code)
        if original_url:
            increment_clicks(short_code)
            app.logger.info(f"Redirecting {short_code} to {original_url}")
            return redirect(original_url)
        app.logger.warning(f"URL not found for short_code: {short_code}")
        return render_template('redirect.html', error="URL not found")
    except Exception as e:
        app.logger.error(f"Error in redirect_to_url: {e}")
        return render_template('redirect.html', error="An error occurred")

@app.route('/stats/<short_code>')
@login_required
def show_stats(short_code):
    try:
        original_url = get_url(short_code)
        clicks = get_clicks(short_code)
        if original_url:
            return render_template('stats.html', short_code=short_code, original_url=original_url, clicks=clicks)
        app.logger.warning(f"Stats not found for short_code: {short_code}")
        return render_template('redirect.html', error="URL not found")
    except Exception as e:
        app.logger.error(f"Error in show_stats: {e}")
        return render_template('redirect.html', error="An error occurred")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

# Rute untuk Privacy Policy
@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

# Rute untuk Terms of Service
@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

# Rute untuk Contact Us
@app.route('/contact-us')
def contact_us():
    return render_template('contact_us.html')

@app.before_request
def before_request():
    if not request.is_secure and not app.debug:
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)
    
from flask import send_file

# Rute untuk sitemap.xml
@app.route('/sitemap.xml')
def sitemap():
    return send_file('sitemap.xml', mimetype='application/xml')

# Rute untuk robots.txt
@app.route('/robots.txt')
def robots():
    return send_file('robots.txt', mimetype='text/plain')

from flask import make_response

@app.after_request
def add_header(response):
    # Cache file statis selama 1 hari
    if 'static' in request.path:
        response.headers['Cache-Control'] = 'public, max-age=86400'
    return response