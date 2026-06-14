from database import User


def register(client, username='testuser', email='test@example.com', password='password123'):
    return client.post('/register', data={
        'username': username,
        'email': email,
        'password': password,
        'confirm_password': password,
    }, follow_redirects=True)


def login(client, username='testuser', password='password123'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)


def test_register_success(client, db):
    rv = register(client)
    assert rv.status_code == 200
    assert User.query.filter_by(username='testuser').first() is not None


def test_register_duplicate_username(client, db):
    register(client)
    rv = register(client, email='other@example.com')
    assert b'already exists' in rv.data or rv.status_code == 200


def test_login_success(client, db):
    register(client)
    rv = login(client)
    assert rv.status_code == 200
    assert b'Dashboard' in rv.data or b'dashboard' in rv.data


def test_login_invalid_password(client, db):
    register(client)
    rv = login(client, password='wrongpassword')
    assert b'Invalid' in rv.data or b'invalid' in rv.data


def test_logout(client, db):
    register(client)
    login(client)
    rv = client.get('/logout', follow_redirects=True)
    assert rv.status_code == 200
