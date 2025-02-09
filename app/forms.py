from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, SelectField, IntegerField, SelectMultipleField, DecimalField
from wtforms.validators import DataRequired, Email, EqualTo, NumberRange, Optional, InputRequired
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm password'),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class QueryForm(FlaskForm):
    keywords = StringField('Search Terms', validators=[DataRequired()])
    min_price = DecimalField('Minimum Price', places=2, validators=[Optional()])
    max_price = DecimalField('Maximum Price', places=2, validators=[Optional()])
    check_interval = IntegerField(
        'Check Every (minutes)', 
        validators=[InputRequired(), NumberRange(min=1, max=1440)]
    )
    submit = SubmitField('Save Search')

class DeleteForm(FlaskForm):
    submit = SubmitField('Delete') 