import sys
from os.path import abspath, dirname

# Add project root to Python path
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from app import create_app
from app.models import db, Query, User

app = create_app()

with app.app_context():
    # Get existing user
    user = User.query.first()
    
    # Create test query
    query = Query(
        keywords='manual-test',
        check_interval=60,
        user_id=user.id
    )
    db.session.add(query)
    db.session.commit()
    
    print("Queries:", Query.query.all())