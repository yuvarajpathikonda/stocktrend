import os

class Config:
    SECRET_KEY = 'Profit2025@'
    MYSQL_HOST = '127.0.0.1'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = 'admin'  # Set your MySQL root password if needed
    MYSQL_DB = 'tradingapp'
    UPLOAD_FOLDER = 'uploads'  # Folder to store uploaded files
    ALLOWED_EXTENSIONS = {'csv'}  # Allow only CSV files to be uploaded
