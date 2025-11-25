from .models import Subject, Post, Comment, Vote, Test, TestQuestion, Question
from django.db.models import Count, Sum
from django.utils import timezone


def question_count():
    return Question.objects.count()

# PRESENT
def subject_tests(subject_id):
    now = timezone.now()
    qs = Test.objects.filter(subject_id=subject_id).order_by('-created_at')
    return [
        {
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'time_limit': t.time_limit,
            'ends_at': t.ends_at,
            'created_at': t.created_at,
            'max_attempts': getattr(t, 'max_attempts', None),
            'is_active': (t.ends_at is None) or (t.ends_at > now)
        }
        for t in qs
    ]
    
def subject_posts(subject_id):
    qs = Post.objects.filter(subject_id=subject_id).select_related('author').annotate(comment_count=Count('comment')).order_by('created_at')
    return [
        {
            'id': p.id,
            'title': p.title,
            'content': p.content,
            'view_count': p.view_count,
            'created_at': p.created_at,
            'author': {
                'id': p.author.id if p.author else None,
                'username': p.author.username if p.author else None
            },
            'comment_count': p.comment_count or 0
        }
        for p in qs
    ]
    
def posts_with_attachment(count):
    count = max(count, -1)
    qs = Post.objects.filter(attachment_path__isnull=False).select_related('subject').order_by('-updated_at', '-created_at')
    if count >= 0:
        qs = qs[:count]
    return [
        {
            'id': p.id,
            'title': p.title,
            'content': p.content,
            'subject': p.subject.name if p.subject else None,
            'updated_at': p.updated_at or p.created_at,
        }
        for p in qs
    ]
    
def popular_posts(count):
    count = max(count, -1)
    qs = Post.objects.select_related('author', 'subject').annotate(
        comment_count=Count('comment'),
        vote_value=Sum('vote__vote_value')
    ).order_by('-view_count')
    if count >= 0:
        qs = qs[:count]
    return [
        {
            'id': p.id,
            'title': p.title,
            'created_at': p.created_at,
            'username': p.author.username if p.author else None,
            'author_avatar_path': p.author.avatar_path if p.author else None,
            'subject_name': p.subject.name if p.subject else None,
            'view_count': p.view_count,
            'comment_count': p.comment_count or 0,
            'vote_value': p.vote_value or 0,
        }
        for p in qs
    ]
    
def latest_posts(count):
    count = max(count, -1)
    qs = Post.objects.select_related('author', 'subject').annotate(
        comment_count=Count('comment'),
        vote_value=Sum('vote__vote_value')
    ).order_by('-created_at')
    if count >= 0:
        qs = qs[:count]
    return [
        {
            'id': p.id,
            'title': p.title,
            'created_at': p.created_at,
            'username': p.author.username if p.author else None,
            'author_avatar_path': p.author.avatar_path if p.author else None,
            'subject_name': p.subject.name if p.subject else None,
            'view_count': p.view_count,
            'comment_count': p.comment_count or 0,
            'vote_value': p.vote_value or 0,
        }
        for p in qs
    ]
    
# PRESENT
def latest_tests(count):
    count = max(count, -1)
    qs = Test.objects.select_related('author', 'subject').order_by('-created_at')
    if count >= 0:
        qs = qs[:count]

    results = []
    for t in qs:
        qcount = TestQuestion.objects.filter(test_id=t.id).count()
        results.append({
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'time_limit': t.time_limit,
            'created_at': t.created_at,
            'ends_at': t.ends_at,
            'author_name': t.author.username if t.author else None,
            'author_avatar_path': t.author.avatar_path if t.author else None,
            'subject_name': t.subject.name if t.subject else None,
            'question_count': qcount,
        })

    return results
    
def insert_post(title, content, subject_id, user_id, attachment_path):
    # Create using ORM and return instance id
    try:
        subject = Subject.objects.get(pk=subject_id)
    except Subject.DoesNotExist:
        subject = None
    try:
        author = None
        from accounts.models import User
        author = User.objects.get(pk=user_id)
    except Exception:
        author = None
    p = Post.objects.create(
        title=title,
        content=content,
        subject=subject,
        author=author,
        attachment_path=attachment_path or None,
    )
    return p.id