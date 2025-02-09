from cryptography.fernet import Fernet
from flask import current_app

class DataEncryptor:
    def __init__(self):
        self.cipher = None
        
    def init_app(self, app):
        self.cipher = Fernet(app.config['ENCRYPTION_KEY'])
    
    def encrypt(self, data):
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data):
        return self.cipher.decrypt(encrypted_data.encode()).decode() 