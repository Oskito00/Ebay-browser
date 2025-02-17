from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, SelectField, IntegerField, SelectMultipleField, DecimalField
from wtforms.validators import DataRequired, Email, EqualTo, NumberRange, Optional, InputRequired, Regexp
from flask_wtf.csrf import CSRFProtect
from app.ebay.constants import MARKETPLACE_IDS

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
    required_keywords = StringField('Required Keywords', validators=[Optional()])
    excluded_keywords = StringField('Excluded Keywords', validators=[Optional()])
    marketplace = SelectField(
    'Marketplace',
    choices=[
        (m['code'], f"{m['country']} ({m['site']})") 
        for m in MARKETPLACE_IDS.values()
    ],
    default='EBAY_GB'
)
    item_location = SelectField(
        'Item Location',
        choices=[
            (l['location'], f"{l['country']}") 
            for l in MARKETPLACE_IDS.values()
        ],
        default='GB'
    )

    condition = SelectField(
        'Condition',
        choices=[
            ('', 'Any Condition'),  # Default
            ('NEW', 'New'),
            ('USED', 'Used'),
        ],
        default=''
    )

    buying_options = SelectField(
        'Buying Options',
        choices=[
            ('FIXED_PRICE|AUCTION', 'Any'),  # Default
            ('FIXED_PRICE', 'Buy It Now'),
            ('AUCTION', 'Auction'),
        ],
        default='FIXED_PRICE|AUCTION'
    )

    submit = SubmitField('Save Search')

class DeleteForm(FlaskForm):
    submit = SubmitField('Delete')

class TelegramConnectForm(FlaskForm):
    chat_id = StringField('Chat ID', validators=[
        DataRequired(),
        Regexp(r'^\d+$', message="Must be numeric")
    ]) 

class TelegramDisconnectForm(FlaskForm):
    pass  # Only needs CSRF token 