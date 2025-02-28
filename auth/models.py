from utilities.database import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    pin = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'