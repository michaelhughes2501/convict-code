from database import ForumPost


def register_and_login(client):
    client.post('/register', data={
        'username': 'forumuser',
        'email': 'forum@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
    })
    client.post('/login', data={'username': 'forumuser', 'password': 'password123'})


def test_forum_loads(client, db):
    rv = client.get('/forum')
    assert rv.status_code == 200


def test_create_post(client, db):
    register_and_login(client)
    rv = client.post('/forum/new', data={
        'title': 'Test Post',
        'content': 'Test content here',
        'category': 'General',
    }, follow_redirects=True)
    assert rv.status_code == 200
    assert ForumPost.query.filter_by(title='Test Post').first() is not None


def test_view_post_unauthenticated(client, db):
    register_and_login(client)
    client.post('/forum/new', data={
        'title': 'Public Post',
        'content': 'Visible to all',
        'category': 'General',
    })
    client.get('/logout')
    post = ForumPost.query.first()
    if post:
        rv = client.get(f'/forum/post/{post.id}')
        assert rv.status_code == 200


def test_add_comment(client, db):
    register_and_login(client)
    client.post('/forum/new', data={
        'title': 'Comment Test',
        'content': 'Post content',
        'category': 'General',
    })
    post = ForumPost.query.first()
    if post:
        rv = client.post(f'/forum/post/{post.id}/comment',
                         data={'content': 'A test comment'}, follow_redirects=True)
        assert rv.status_code == 200
