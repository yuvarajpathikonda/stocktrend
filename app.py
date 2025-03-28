import os
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
import plotly.express as px
import pandas as pd
import mysql.connector
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import time  # For Unix timestamp conversion
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object('config.Config')
bcrypt = Bcrypt(app)

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
app.config['SECRET_KEY'] = 'your_secret_key'  # Required for session management
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Set session timeout to 30 minutes

# Connect to MySQL
db = mysql.connector.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    database=app.config['MYSQL_DB']
)
db.commit()
cursor = db.cursor()

@app.before_request
def make_session_permanent():
    session.permanent = True  # Makes session respect the timeout

from flask import Flask, session, redirect, flash, url_for, request
from datetime import datetime, timedelta
import time  # For Unix timestamp conversion

app.config['SECRET_KEY'] = 'your_secret_key'  
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  

@app.before_request
def check_session_timeout():
    if 'user' in session:
        last_activity = session.get('last_activity')

        if last_activity and (time.time() - last_activity) > 1800:  # 30 minutes = 1800 seconds
            session.pop('user', None)
            session.pop('last_activity', None)
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for('login'))

        # Update last activity timestamp (store as Unix timestamp)
        session['last_activity'] = time.time()


# Home Route
@app.route('/', methods=['GET', 'POST'])
def home():
    return redirect('/login')

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
            db.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect('/')
        except:
            flash("Email already exists!", "danger")
            return redirect('/register')

    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT SQL_NO_CACHE * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user[3], password):
            session['user'] = user[1]
            session['last_activity'] = time.time()  # Set session activity time
            flash("Login successful!", "success")
            return redirect('/dashboard')
        else:
            flash("Invalid email or password!", "danger")
            return redirect('/')

    return render_template('login.html')

# Dashboard Route
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user' not in session:
        flash("Please log in first!", "warning")
        return redirect('/')

    return render_template('dashboard.html', user=session['user'])

# Search Route
@app.route('/stock_search', methods=['GET'])
def stock_search():
    if 'user' not in session:
        flash("Please log in first!", "warning")
        return redirect('/')
    
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of records per page
    offset = (page - 1) * per_page

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    ticker = request.args.get('ticker', '')
    unit = request.args.get('price_unit', '')
    mrktCapStart = request.args.get('mrktCapStart', '')
    mrktCapEnd = request.args.get('mrktCapEnd', '')
    dollarVolStart = request.args.get('dollarVolStart', '')
    dollarVolEnd = request.args.get('dollarVolEnd', '')

    query = "SELECT SQL_NO_CACHE * FROM trading_data WHERE 1=1"
    total_records_query = "SELECT SQL_NO_CACHE COUNT(*) FROM trading_data WHERE 1=1"
    params = []

    if start_date:
        query += " AND date >= %s"
        total_records_query += " AND date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND date <= %s"
        total_records_query += " AND date <= %s"
        params.append(end_date)

    if ticker:
        query += " AND ticker LIKE %s"
        total_records_query += " AND ticker LIKE %s"
        params.append(f"%{ticker}%")    
    
    if mrktCapStart:
        query += " AND market_cap >= %s"
        total_records_query += " AND market_cap >= %s"
        params.append(convert_value(unit,mrktCapStart))

    if mrktCapEnd:
        query += " AND market_cap <= %s"
        total_records_query += " AND market_cap <= %s"
        params.append(convert_value(unit,mrktCapEnd))
    
    if dollarVolStart:
        query += " AND volume_price >= %s"
        total_records_query += " AND volume_price >= %s"
        params.append(convert_value(unit,dollarVolStart))
    
    if dollarVolEnd:
        query += " AND volume_price <= %s"
        total_records_query += " AND volume_price <= %s"
        params.append(convert_value(unit,dollarVolEnd))
    db.commit()
    cursor.execute(total_records_query, tuple(params))
    total_records = cursor.fetchone()[0]
    total_pages = (total_records + per_page - 1) // per_page  # Calculate total pages
    query += " ORDER BY ticker ASC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    
    cursor.execute(query, tuple(params))
    raw_data = cursor.fetchall()

    data = [{"date": row[1].strftime("%Y-%m-%d"), "ticker": row[2], "companyname": row[3], "change_perc": row[4],
            "volume_price": row[5], "volume_price_formatted": format_value(row[5]), "market_cap": row[6], "market_cap_formatted": format_value(row[6]), "industry": row[7]} for row in raw_data]

    return render_template('stock_search.html', user=session['user'], data=data, page=page, total_pages=total_pages)

# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out successfully.", "info")
    return redirect('/')


# Fetch stock data with optional date range filter
@app.route('/scatter_chart')
def scatter_chart():
    if 'user' not in session:
        flash("Please log in first!", "warning")
        return redirect('/')

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    ticker = request.args.get('ticker', '')
    unit = request.args.get('price_unit', '')
    mrktCapStart = request.args.get('mrktCapStart', '')
    mrktCapEnd = request.args.get('mrktCapEnd', '')
    dollarVolStart = request.args.get('dollarVolStart', '')
    dollarVolEnd = request.args.get('dollarVolEnd', '')


    query = "SELECT SQL_NO_CACHE * FROM trading_data WHERE 1=1 "
    distinct_tickers = "SELECT SQL_NO_CACHE DISTINCT ticker FROM trading_data WHERE 1=1 "
    params = []

    if start_date:
        query += " AND date >= %s"
        distinct_tickers += " AND date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND date <= %s"
        distinct_tickers += " AND date <= %s"
        params.append(end_date)

    if ticker:
        query += " AND ticker LIKE %s"
        distinct_tickers += " AND ticker LIKE %s"
        params.append(f"%{ticker}%")
    
    if mrktCapStart:
        query += " AND market_cap >= %s"
        distinct_tickers += " AND market_cap >= %s"
        params.append(convert_value(unit,mrktCapStart))

    if mrktCapEnd:
        query += " AND market_cap <= %s"
        distinct_tickers += " AND market_cap <= %s"
        params.append(convert_value(unit,mrktCapEnd))
    
    if dollarVolStart:
        query += " AND volume_price >= %s"
        distinct_tickers += " AND volume_price >= %s"
        params.append(convert_value(unit,dollarVolStart))
    
    if dollarVolEnd:
        query += " AND volume_price <= %s"
        distinct_tickers += " AND volume_price <= %s"
        params.append(convert_value(unit,dollarVolEnd))

    query += " ORDER BY ticker ASC"
    distinct_tickers += " ORDER BY ticker ASC"

    print("Executing SQL Query:", query, distinct_tickers, params)  # Debugging log

    db.commit()
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.execute(distinct_tickers, tuple(params))
    tickers = {ticker: index for index, (ticker,) in enumerate(cursor.fetchall())}

    if not rows:
        print(f"No data found between {start_date} and {end_date}")

    data = [{"x": row[1].strftime("%Y-%m-%d"), 
             "y": row[2], 
             "ticker": row[2],
             "companyname": row[3],
             "change_perc": row[4],
             "volume_price_raw": row[5],
             "volume_price": format_value(row[5]),
             "market_cap": format_value(row[6]),
             "industry": row[7]
             } for row in rows]
    print(list(tickers.keys()), data)  # Debugging log
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Get unique tickers for Y-axis ordering
    unique_tickers = df["y"].unique()[::-1]  # Reverse to match order from top to bottom
    ticker_indices = list(range(len(unique_tickers)))  # Assign indices to tickers
    ticker_map = dict(zip(unique_tickers, ticker_indices))  # Mapping tickers to indices
    df["ticker"] = df["y"].map(ticker_map)  # Map tickers to numeric Y values

    # Bubble Chart
    fig = px.scatter(df, x="x", y="ticker", size="volume_price_raw", color="change_perc",
                 hover_data={"x":False,"volume_price_raw":False,"companyname":True, "industry":True, "market_cap":True, "volume_price":True},
                 labels={"x": "Date", "y": "Stock Index", "ticker": "Ticker","change_perc": "Change (%)", "companyname": "Company Name", "industry": "Industry", "market_cap": "Market Cap", "volume_price": "Volume Price"},
                 title="Stock Volume Bubble Chart")

    # Adjust bubble opacity and color scale
    # Improve Layout
    fig.update_traces(textposition='middle right')  # Position text inside the bubble
    fig.update_layout(
        yaxis=dict(
            title="Ticker Name",
            tickmode="array",
            tickvals=ticker_indices,  # Ensure all tickers are shown
            ticktext=unique_tickers,  # Show actual ticker names
            range=[-0.5, len(unique_tickers) - 0.5],  # Adjust range to fit all tickers
            fixedrange=False,  # Allow scrolling
        ),
        xaxis=dict(
            tickformat="%Y-%m-%d",  # Format as Date only
            type="category" if len(df) < 5 else "date",  # Force categorical if fewer records
        ),
        showlegend=False,
        height=1000,  # Reduce height to enable scrolling
        margin=dict(l=150, r=50, t=50, b=50),  # Adjust margins for better view
    )
    graph_html = fig.to_html(full_html=False)
    
    return render_template("scatter_chart.html", graph_html=graph_html)

# Function to Check Allowed File Extensions
def allowed_file(filename):
    print(app.config)
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to Read and Insert CSV Data
def insert_csv_data(csv_file):
    try:
        df = pd.read_csv(csv_file)  # Read CSV into DataFrame
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for _, row in df.iterrows():
            sql = """
                INSERT INTO trading_data (date, ticker, companyname, change_perc, volume_price, market_cap, industry)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (current_date, row['Ticker'], row['Description'], row['Change %'], row['Volume*Price'], row['Market Capitalization'], row['Industry'])
            cursor.execute(sql, values)
        
        db.commit()
        print("Data inserted successfully!")
        return True
    except Exception as e:
        print("Error:", e)
        return False

# Route to Upload CSV
@app.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    if 'user' not in session:
        flash("Please log in first!", "warning")
        return redirect('/')
        
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file selected!", "danger")
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash("No file selected!", "danger")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)  # Save the uploaded file

            if insert_csv_data(file_path):  # Insert data into MySQL
                flash("CSV data inserted successfully!", "success")
            else:
                flash("Error processing CSV file!", "danger")

            return redirect('/dashboard')

    return render_template('upload.html')

@app.route('/reset_session')
def reset_session():
    if 'user' in session:
        session['last_activity'] = time.time()  # Reset session timer
    return '', 204  # No content response

def format_value(value):
    if value >= 10000000:  # 1 Crore = 10,000,000
        return f"{round(value / 10000000, 2)} Cr"
    elif value >= 100000:  # 1 Lakh = 100,000
        return f"{round(value / 100000, 2)} L"
    else:
        return f"{value}"  # Keep original value if less than 1 lakh

def convert_value(unit,value):
        """Convert Market Cap from 'Cr' or 'Lakh' to numeric value in crores."""
        if "Cr" in unit:
            return float(value) * 10000000
        elif "L" in unit:
            return float(value) *100000  
        return 0    

if __name__ == '__main__':
    app.run(debug=True)
