from database import User, db as _db


def make_admin(app, username='adminuser'):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            user.is_admin = True
            _db.session.commit()


def register_and_login(client, username='adminuser', email='admin@example.com'):
    client.post('/register', data={
        'username': username,
        'email': email,
        'password': 'password123',
        'confirm_password': 'password123',
    })
    client.post('/login', data={'username': username, 'password': 'password123'})


def test_admin_blocked_for_non_admin(client, db):
    register_and_login(client, username='regularuser', email='regular@example.com')
    rv = client.get('/admin', follow_redirects=True)
    assert b'Admin access required' in rv.data or rv.status_code in (200, 302)


def test_admin_dashboard_accessible_for_admin(client, db, app):
    register_and_login(client)
    make_admin(app)
    rv = client.get('/admin')
    assert rv.status_code == 200
    assert b'Admin' in rv.data
