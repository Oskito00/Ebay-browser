from flask_wtf import FlaskForm
from wtforms import FieldList, HiddenField, StringField, PasswordField, SubmitField, FloatField, SelectField, IntegerField, SelectMultipleField, DecimalField
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
        validators=[InputRequired(), NumberRange(min=5, max=120)]
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
    main_chat_id = StringField('Main Chat ID', validators=[
        DataRequired(),
        Regexp(r'^\d+$', message="Must be numeric")
    ])
    additional_chat_ids = FieldList(
        StringField('Additional Chat ID', validators=[
            Optional(),
            Regexp(r'^\d+$', message="Must be numeric")
        ]),
        min_entries=0,
        max_entries=5
    )
    submit = SubmitField('Save')

class TelegramDisconnectForm(FlaskForm):
    pass  # Only needs CSRF token 

class SubscriptionActionForm(FlaskForm):
    tier = StringField('tier')
    action = StringField('action')
    submit = SubmitField('Submit')
    when = StringField('when')
