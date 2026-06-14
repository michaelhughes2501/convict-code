"""
Dashboard routes and utilities for ConvictCode
Includes admin dashboard, user analytics, and resource management
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime, timedelta
from database import db, User, Message, ForumPost, Match, Like
import anthropic

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

@dashboard_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """Get dashboard statistics"""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    stats = {
        'total_users': User.query.count(),
        'total_messages': Message.query.count(),
        'total_posts': ForumPost.query.count(),
        'total_matches': Match.query.filter_by(is_mutual=True).count(),
        'active_users_week': User.query.filter(User.last_login >= week_ago).count(),
        'new_users_week': User.query.filter(User.created_at >= week_ago).count(),
        'messages_week': Message.query.filter(Message.created_at >= week_ago).count(),
        'posts_week': ForumPost.query.filter(ForumPost.created_at >= week_ago).count(),
        'new_users_month': User.query.filter(User.created_at >= month_ago).count(),
        'engagement_rate': calculate_engagement_rate(),
    }
    
    return jsonify(stats)

@dashboard_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    """Get all users for admin dashboard"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    users = User.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'users': [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'created_at': u.created_at.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'matches': Match.query.filter(
                ((Match.user1_id == u.id) | (Match.user2_id == u.id)) &
                (Match.is_mutual == True)
            ).count(),
        } for u in users.items],
        'total': users.total,
        'pages': users.pages,
        'current_page': page,
    })

@dashboard_bp.route('/user/<int:user_id>/profile', methods=['GET'])
@login_required
@admin_required
def get_user_profile(user_id):
    """Get detailed user profile"""
    user = User.query.get_or_404(user_id)
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'age': user.age,
        'location': user.location,
        'bio': user.bio,
        'created_at': user.created_at.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'messages_sent': Message.query.filter_by(sender_id=user_id).count(),
        'messages_received': Message.query.filter_by(recipient_id=user_id).count(),
        'posts_created': ForumPost.query.filter_by(user_id=user_id).count(),
        'matches': Match.query.filter(
            ((Match.user1_id == user_id) | (Match.user2_id == user_id)) &
            (Match.is_mutual == True)
        ).count(),
        'likes_given': Like.query.filter_by(user_id=user_id).count(),
        'likes_received': Like.query.filter_by(liked_user_id=user_id).count(),
    })

@dashboard_bp.route('/ai/generate-response', methods=['POST'])
@login_required
def generate_ai_response():
    """Generate AI-powered response for user"""
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt', '').strip()
    context = data.get('context', 'general')
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    try:
        client = anthropic.Anthropic(api_key=current_app.config.get('ANTHROPIC_API_KEY'))
        
        system_prompts = {
            'general': "You are a helpful support assistant for a reentry community platform.",
            'profile': "You are helping a user write their profile bio. Be encouraging and professional.",
            'forum': "You are helping moderate forum discussions. Be fair and constructive.",
            'message': "You are helping draft a message. Be warm and respectful.",
        }
        
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            system=system_prompts.get(context, system_prompts['general']),
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        return jsonify({'response': response.content[0].text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/ai/recommend-matches', methods=['GET'])
@login_required
def recommend_matches():
    """AI-powered match recommendations"""
    user = current_user
    
    # Get users user hasn't seen
    seen_users = db.session.query(Like.liked_user_id).filter_by(user_id=user.id).all()
    seen_ids = [s[0] for s in seen_users]
    
    candidates = User.query.filter(
        (User.id != user.id) &
        (User.id.notin_(seen_ids))
    ).limit(5).all()
    
    recommendations = []
    for candidate in candidates:
        score = calculate_match_score(user, candidate)
        recommendations.append({
            'id': candidate.id,
            'username': candidate.username,
            'age': candidate.age,
            'location': candidate.location,
            'bio': candidate.bio[:100],
            'match_score': score,
        })
    
    return jsonify(sorted(recommendations, key=lambda x: x['match_score'], reverse=True))

@dashboard_bp.route('/ai/analyze-sentiment', methods=['POST'])
@login_required
def analyze_sentiment():
    """Analyze sentiment of user content"""
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    try:
        client = anthropic.Anthropic(api_key=current_app.config.get('ANTHROPIC_API_KEY'))
        
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=100,
            system="Analyze the sentiment of this text and respond with only: positive, neutral, or negative",
            messages=[{'role': 'user', 'content': text}]
        )
        
        sentiment = response.content[0].text.lower().strip()
        
        return jsonify({'sentiment': sentiment})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/activity-log', methods=['GET'])
@login_required
@admin_required
def get_activity_log():
    """Get recent activity log"""
    limit = request.args.get('limit', 50, type=int)
    
    activities = []
    
    # Recent messages
    messages = Message.query.order_by(Message.created_at.desc()).limit(limit).all()
    for msg in messages:
        activities.append({
            'type': 'message',
            'user': msg.sender.username,
            'action': f"sent message to {msg.recipient.username}",
            'timestamp': msg.created_at.isoformat(),
        })
    
    # Recent posts
    posts = ForumPost.query.order_by(ForumPost.created_at.desc()).limit(limit).all()
    for post in posts:
        activities.append({
            'type': 'post',
            'user': post.user.username,
            'action': f"created post: {post.title[:50]}",
            'timestamp': post.created_at.isoformat(),
        })
    
    # Recent matches
    matches = Match.query.filter_by(is_mutual=True).order_by(Match.created_at.desc()).limit(limit).all()
    for match in matches:
        activities.append({
            'type': 'match',
            'user': match.user1.username,
            'action': f"matched with {match.user2.username}",
            'timestamp': match.created_at.isoformat(),
        })
    
    return jsonify(sorted(activities, key=lambda x: x['timestamp'], reverse=True)[:limit])

def calculate_engagement_rate():
    """Calculate platform engagement rate"""
    total_users = User.query.count()
    if total_users == 0:
        return 0
    
    week_ago = datetime.utcnow() - timedelta(days=7)
    active_users = User.query.filter(User.last_login >= week_ago).count()
    
    return (active_users / total_users) * 100

def calculate_match_score(user1, user2):
    """Calculate compatibility score between two users"""
    score = 0
    
    # Age proximity (max 25 points)
    if user1.age and user2.age:
        age_diff = abs(user1.age - user2.age)
        if age_diff <= 5:
            score += 25
        elif age_diff <= 10:
            score += 15
        else:
            score += 5
    
    # Location proximity (max 25 points)
    if user1.location and user2.location:
        if user1.location.lower() == user2.location.lower():
            score += 25
        else:
            score += 10
    
    # Common interests (max 25 points)
    if user1.bio and user2.bio:
        common_words = len(set(user1.bio.lower().split()) & set(user2.bio.lower().split()))
        score += min(common_words * 2, 25)
    
    # Rehabilitation alignment (max 25 points)
    if user1.rehabilitation_status and user2.rehabilitation_status:
        if user1.rehabilitation_status == user2.rehabilitation_status:
            score += 25
        else:
            score += 10
    
    return min(score, 100)
