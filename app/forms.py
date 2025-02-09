from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, NumberRange

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
    min_price = FloatField('Minimum Price')
    max_price = FloatField('Maximum Price')
    condition = SelectField('Condition', choices=[
        ('', 'Any'),
        ('1000', 'New'),
        ('3000', 'Used'),
        ('4000', 'Very Good'),
        ('5000', 'Good'),
        ('6000', 'Acceptable')
    ])
    check_interval = IntegerField('Check Every (minutes)', validators=[
        NumberRange(min=15, max=1440)
    ])
    submit = SubmitField('Save')

class DeleteForm(FlaskForm):
    submit = SubmitField('Delete') 