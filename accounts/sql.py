from django.db import connection
from .models import User, Student, Teacher, Major, Department
from forum.models import Submission, Test
from django.db.models import Q


def user_count():
    return User.objects.count()


# PRESENT
def one_user(user_id=None, username=None, email=None):
    qs = User.objects.all()
    if user_id is not None:
        qs = qs.filter(pk=user_id)
    if username is not None:
        qs = qs.filter(username=username)
    if email is not None:
        qs = qs.filter(email=email) if (user_id is None and username is None) else qs | User.objects.filter(email=email)
    user = qs.first()
    if not user:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'password': user.password,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'avatar_path': user.avatar_path,
    }

def one_student(user_id):
    try:
        s = Student.objects.select_related('major').get(pk=user_id)
        return {
            'major_id': s.major.id if s.major else None,
            'major_name': s.major.name if s.major else None,
            'enrollment_year': s.enrollment_year,
            'student_code': s.student_code
        }
    except Student.DoesNotExist:
        return None

def one_teacher(user_id):
    try:
        t = Teacher.objects.select_related('department').get(pk=user_id)
        return {
            'title': t.title,
            'department_id': t.department.id if t.department else None,
            'department_name': t.department.name if t.department else None,
            'degree': t.degree,
            'teacher_code': t.teacher_code
        }
    except Teacher.DoesNotExist:
        return None

# PRESENT
def insert_user(username, email, password, first_name, last_name, user_type):
    user = User.objects.create(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    # legacy student/teacher tables: leave creation to existing raw SQL behavior if needed
    return user.id

def update_user_name(first_name, last_name, user_id):
    User.objects.filter(pk=user_id).update(first_name=first_name, last_name=last_name)

def update_user_avatar(avatar_path, user_id):
    User.objects.filter(pk=user_id).update(avatar_path=avatar_path)

def update_student(user_id, major_id, enrollment_year, student_code):
    obj, created = Student.objects.update_or_create(
        id=user_id,
        defaults={
            'student_code': student_code,
            'enrollment_year': enrollment_year,
            'major_id': major_id
        }
    )
    return obj

def update_teacher(user_id, title, teacher_code, degree, department_id):
    obj, created = Teacher.objects.update_or_create(
        id=user_id,
        defaults={
            'title': title,
            'teacher_code': teacher_code,
            'degree': degree,
            'department_id': department_id
        }
    )
    return obj




def all_subject():
    from forum.models import Subject
    return [
        {'id': s.id, 'name': s.name, 'description': s.description}
        for s in Subject.objects.all()
    ]
    
def one_subject(subject_id):
    from forum.models import Subject
    try:
        s = Subject.objects.get(pk=subject_id)
        return {'id': s.id, 'name': s.name, 'description': s.description}
    except Subject.DoesNotExist:
        return None
    
def all_major():
    return [{'id': m.id, 'name': m.name, 'department_id': m.department.id if m.department else None} for m in Major.objects.all()]
        
def all_department():
    return [{'id': d.id, 'name': d.name} for d in Department.objects.order_by('name')]

def user_submission_count(user_id):
    return Submission.objects.filter(author_id=user_id).count()
    
def user_post_count(user_id):
    from forum.models import Post
    return Post.objects.filter(author_id=user_id).count()
    
def user_test_count(user_id):
    from forum.models import Test
    return Test.objects.filter(author_id=user_id).count()


def user_recent_submissions(user_id, count):
    count = max(count, -1)
    qs = Submission.objects.filter(author_id=user_id).select_related('test').order_by('-created_at')
    if count >= 0:
        qs = qs[:count]
    return [{'title': s.test.title if s.test else None, 'created_at': s.created_at} for s in qs]
    
# PRESENT
def user_recent_posts(user_id, count):
    count = max(count, -1)
    from forum.models import Post
    qs = Post.objects.filter(author_id=user_id).order_by('-created_at')
    if count >= 0:
        qs = qs[:count]
    return [{'title': p.title, 'created_at': p.created_at} for p in qs]
    
def user_recent_tests(user_id, count):
    count = max(count, -1)
    from forum.models import Test
    qs = Test.objects.filter(author_id=user_id).order_by('-created_at')
    if count >= 0:
        qs = qs[:count]
    return [{'title': t.title, 'created_at': t.created_at} for t in qs]
    