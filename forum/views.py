import os
import uuid
import json
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.db.models import F, Sum
from django.utils import timezone
from .models import Post, Comment, Vote, Subject, Question, MultipleChoiceOption, MultipleChoiceQuestion, EssayQuestion, TestQuestion, Submission, Test, Answer, MultipleChoiceAnswer, EssayAnswer
from django.http import Http404
from django.shortcuts import render, redirect

import accounts.sql
from . import sql

# new helper: find a relation field name on model_cls that relates to target_model
def _get_relation_field_name(model_cls, target_model):
	# Look for OneToOneField / ForeignKey that points to target_model
	for f in model_cls._meta.get_fields():
		# f.related_model available on Django relation fields
		if getattr(f, 'related_model', None) is target_model:
			return f.name
	return None

# helper to try creating a related object using a few candidate relation keys
def _create_with_relation(model_cls, target_instance, extra_kwargs=None):
	"""
	Try to create an instance of model_cls linked to target_instance.
	Tries: detected relation field name, '<target>','<target>_id', then 'id' (pk).
	Returns created instance or raises the last exception.
	"""
	extra_kwargs = dict(extra_kwargs or {})
	target_model = target_instance.__class__
	# 1) detected relation field
	rel_field = _get_relation_field_name(model_cls, target_model)
	last_exc = None
	if rel_field:
		try:
			kwargs = dict(extra_kwargs)
			kwargs[rel_field] = target_instance
			return model_cls.objects.create(**kwargs)
		except Exception as e:
			last_exc = e

	# 2) try common candidate names
	candidate = target_model.__name__.lower()
	for key, use_id in ((candidate, False), (candidate + '_id', True), ('id', True)):
		try:
			kwargs = dict(extra_kwargs)
			kwargs[key] = (getattr(target_instance, 'id') if use_id else target_instance)
			return model_cls.objects.create(**kwargs)
		except Exception as e:
			last_exc = e
			continue

	# If all attempts failed, raise last exception for debugging
	if last_exc:
		raise last_exc
	# fallback safety (shouldn't reach)
	return model_cls.objects.create(**extra_kwargs)

# new helpers: read metadata directly from auxiliary tables to avoid ORM reverse-field issues
def _get_mcq_meta(question_id):
    """Return dict with keys 'correct_option_id' and 'randomize_options' or None."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT correct_option_id, randomize_options FROM multiple_choice_questions WHERE id = ?", [question_id])
            row = cursor.fetchone()
        if row:
            return {'correct_option_id': row[0], 'randomize_options': bool(row[1])}
    except Exception:
        return None
    return None

def _get_essay_meta(question_id):
    """Return dict with key 'word_limit' or None."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT word_limit FROM essay_questions WHERE id = ?", [question_id])
            row = cursor.fetchone()
        if row:
            return {'word_limit': row[0]}
    except Exception:
        return None
    return None

def index(request):
    return render(request, 'forum/index.html', {
        'subjects': accounts.sql.all_subject(),
        'username': request.session.get('username'),
        'is_authenticated': request.session.get('user_id') is not None
    })

def subject_detail(request, subject_id):
    """Chi tiết môn học"""
    
    subject = accounts.sql.one_subject(subject_id)
    if not subject:
        raise Http404("Môn học không tồn tại")
    
    tests = sql.subject_tests(subject_id)
    posts = sql.subject_posts(subject_id)
    user_count = accounts.sql.user_count()
    question_count = sql.question_count()
    
    context = {
        'is_authenticated': request.session.get('user_id') is not None,
        'username': request.session.get('username'),
        'subject': subject,
        'posts': posts,
        'tests': tests,
        'user_count': user_count,
        'question_count': question_count
    }
    return render(request, 'forum/subject_detail.html', context)


def create_post(request):
    """Tạo bài viết mới - Raw SQL"""
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập để đăng bài')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']
    # Ensure user exists in DB (avoid FK error if session is stale)
    try:
        user_id = int(user_id)
    except Exception:
        messages.error(request, 'Phiên đăng nhập không hợp lệ, vui lòng đăng nhập lại')
        return redirect('accounts:login')

    if not accounts.sql.one_user(user_id=user_id):
        messages.error(request, 'Tài khoản không tồn tại, vui lòng đăng nhập lại')
        return redirect('accounts:login')
    subject_id = request.GET.get('subject_id')
    subjects = accounts.sql.all_subject()
    
    if request.method != 'POST':
        context = {
            'is_authenticated': True,
            'username': request.session.get('username'),
            'subjects': subjects,
            'title': 'Tạo bài viết mới',
            'selected_subject_id': int(subject_id) if subject_id else None
        }
        return render(request, 'forum/post_form.html', context)

    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    subject_id = request.POST.get('subject')
    attachment = request.FILES.get('attachment')
        
    errors = []
    if not title:
        errors.append('Tiêu đề không được để trống')
    elif len(title) < 5:
        errors.append('Tiêu đề phải có ít nhất 5 ký tự')
    elif len(title) > 200:
        errors.append('Tiêu đề không được quá 200 ký tự')
        
    if content and len(content) > 50000:
        errors.append('Nội dung quá dài (tối đa 50,000 ký tự)')
        
    if not subject_id:
        errors.append('Vui lòng chọn môn học')
    elif not accounts.sql.one_subject(subject_id):
        errors.append('Môn học không tồn tại')
    
    if errors:
        for error in errors:
            messages.error(request, error)
        context = {
            'is_authenticated': True,
            'username': request.session.get('username'),
            'subjects': subjects,
            'title': 'Tạo bài viết mới',
            'selected_subject_id': int(subject_id) if subject_id else None,
            'form_data': {
                'title': title,
                'content': content,
                'subject': subject_id
            }
        }
        return render(request, 'forum/post_form.html', context)
        
    # file upload
    attachment_path = None
    if attachment:
        # Validate file
        allowed_extensions = ['pdf', 'doc', 'docx', 'txt', 'zip', 'rar']
        file_ext = attachment.name.split('.')[-1].lower()
        if file_ext not in allowed_extensions:
            messages.error(request, 'Định dạng file không hợp lệ')
            context = {
                'is_authenticated': True,
                'username': request.session.get('username'),
                'subjects': subjects,
                'title': 'Tạo bài viết mới',
                'selected_subject_id': int(subject_id) if subject_id else None,
                'form_data': {
                    'title': title,
                    'content': content,
                    'subject': subject_id
                }
            }
            return render(request, 'forum/post_form.html', context)
            
        # Check file size (max 25MB)
        if attachment.size > 25 * 1024 * 1024:
            messages.error(request, 'File quá lớn (tối đa 25MB)')
            context = {
                'is_authenticated': True,
                'username': request.session.get('username'),
                'subjects': subjects,
                'title': 'Tạo bài viết mới',
                'selected_subject_id': int(subject_id) if subject_id else None,
                'form_data': {
                    'title': title,
                    'content': content,
                    'subject': subject_id
                }
            }
            return render(request, 'forum/post_form.html', context)
        
        # Generate unique filename
        unique_name = f"{uuid.uuid4()} {attachment.name}"
        upload_path = os.path.join('posts', unique_name)
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)
        
        # Create directory if not exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file
        with open(full_path, 'wb+') as destination:
            for chunk in attachment.chunks():
                destination.write(chunk)
        
        attachment_path = upload_path
    
    try:
        sql.insert_post(title, content, subject_id, user_id, attachment_path)
        messages.success(request, 'Bài viết đã được đăng thành công!')
        return redirect('forum:subject_detail', subject_id=subject_id)
        
    except Exception as e:
        # Xóa file
        if attachment_path:
            try:
                os.remove(full_path)
            except:
                pass
        
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        context = {
            'is_authenticated': True,
            'username': request.session.get('username'),
            'subjects': subjects,
            'title': 'Tạo bài viết mới',
            'selected_subject_id': int(subject_id) if subject_id else None,
            'form_data': {
                'title': title,
                'content': content,
                'subject': subject_id
            }
        }
        return render(request, 'forum/post_form.html', context)


def edit_post(request, post_id):
    """Chỉnh sửa bài viết"""
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']

    try:
        post_obj = Post.objects.select_related('subject', 'author').get(pk=post_id)
    except Post.DoesNotExist:
        raise Http404("Bài viết không tồn tại")

    if not post_obj.author or post_obj.author.id != user_id:
        messages.error(request, 'Bạn không có quyền chỉnh sửa bài viết này')
        return redirect('forum:post_detail', post_id=post_id)

    post = {
        'id': post_obj.id,
        'title': post_obj.title,
        'content': post_obj.content,
        'subject_id': post_obj.subject.id if post_obj.subject else None,
        'attachment_path': post_obj.attachment_path,
        'author_id': post_obj.author.id if post_obj.author else None,
        'subject': {
            'id': post_obj.subject.id if post_obj.subject else None,
            'name': post_obj.subject.name if post_obj.subject else None
        }
    }

    subjects = list(Subject.objects.order_by('name').values('id', 'name'))
    
    if request.method != 'POST':
        context = {
            'is_authenticated': True,
            'username': request.session.get('username'),
            'subjects': subjects,
            'title': 'Chỉnh sửa bài viết',
            'post': post,
            'form_data': post
        }
        return render(request, 'forum/post_form.html', context)
    
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    subject_id = request.POST.get('subject')
    attachment = request.FILES.get('attachment')
    
    errors = []
    if not title or title.strip() == '':
        errors.append('Tiêu đề không được để trống')
    elif len(title) > 200:
        errors.append('Tiêu đề không được quá 200 ký tự')
        
    if content and len(content) > 50000:
        errors.append('Nội dung quá dài')
        
    if not subject_id:
        errors.append('Vui lòng chọn môn học')
    
    if errors:
        for error in errors:
            messages.error(request, error)
        context = {
            'is_authenticated': True,
            'username': request.session.get('username'),
            'subjects': subjects,
            'title': 'Chỉnh sửa bài viết',
            'post': post,
            'form_data': {
                'title': title,
                'content': content,
                'subject_id': subject_id
            }
        }
        return render(request, 'forum/post_form.html', context)
    
    # Xử lý file mới nếu có
    attachment_path = post['attachment_path']
    if attachment:
        allowed_extensions = ['pdf', 'doc', 'docx', 'txt', 'zip', 'rar']
        file_ext = attachment.name.split('.')[-1].lower()
        
        if file_ext in allowed_extensions and attachment.size <= 25 * 1024 * 1024:
            # Xóa file cũ
            if attachment_path:
                try:
                    old_file = os.path.join(settings.MEDIA_ROOT, attachment_path)
                    if os.path.exists(old_file):
                        os.remove(old_file)
                except:
                    pass
            
            # Lưu file mới
            unique_name = f"{uuid.uuid4()}"
            upload_path = os.path.join('posts', unique_name)
            full_path = os.path.join(settings.MEDIA_ROOT, upload_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'wb+') as destination:
                for chunk in attachment.chunks():
                    destination.write(chunk)
            
            attachment_path = upload_path
        else:
            messages.error(request, 'File không hợp lệ hoặc quá lớn')
            return redirect('forum:edit_post', post_id=post_id)
    
    try:
        # update with ORM
        post_obj.title = title
        post_obj.content = content
        if subject_id:
            try:
                post_obj.subject = Subject.objects.get(pk=subject_id)
            except Subject.DoesNotExist:
                post_obj.subject = None
        post_obj.attachment_path = attachment_path
        post_obj.updated_at = timezone.now()
        post_obj.save()

        messages.success(request, 'Bài viết đã được cập nhật!')
        return redirect('forum:post_detail', post_id=post_id)
    except Exception as e:
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        return redirect('forum:edit_post', post_id=post_id)


def delete_post(request, post_id):
    """Xóa bài viết"""
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']
    try:
        post_obj = Post.objects.select_related('subject', 'author').get(pk=post_id)
    except Post.DoesNotExist:
        raise Http404("Bài viết không tồn tại")

    if not post_obj.author or post_obj.author.id != user_id:
        messages.error(request, 'Bạn không có quyền xóa bài viết này')
        return redirect('forum:post_detail', post_id=post_id)

    attachment_path = post_obj.attachment_path
    subject_id = post_obj.subject.id if post_obj.subject else None

    if attachment_path:
        try:
            file_path = os.path.join(settings.MEDIA_ROOT, attachment_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass

    post_obj.delete()

    messages.success(request, 'Bài viết đã được xóa')
    return redirect('forum:subject_detail', subject_id=subject_id)


def post_detail(request, post_id):
    """Chi tiết bài viết"""
    try:
        p = Post.objects.select_related('subject', 'author').get(pk=post_id)
    except Post.DoesNotExist:
        raise Http404("Bài viết không tồn tại")

    # attachment info
    attachment_path = p.attachment_path
    file_extension = ''
    filename = ''
    file_size = 0
    if attachment_path:
        filename = os.path.basename(attachment_path)
        file_extension = filename.split('.')[-1].lower() if '.' in filename else ''
        parts = filename.split(' ', 1)
        filename = parts[1] if len(parts) > 1 else ''
        try:
            full_path = os.path.join(settings.MEDIA_ROOT, attachment_path)
            file_size = os.path.getsize(full_path)
        except:
            file_size = 0

    # comment count and vote value
    comment_count = Comment.objects.filter(post_id=post_id).count()
    vote_value = Vote.objects.filter(post_id=post_id).aggregate(total=Sum('vote_value'))['total'] or 0

    post = {
        'id': p.id,
        'title': p.title,
        'content': p.content,
        'view_count': p.view_count,
        'created_at': p.created_at,
        'updated_at': p.updated_at,
        'attachment': {
            'url': f"{settings.MEDIA_URL}/{attachment_path}" if attachment_path else None,
            'size': file_size
        } if attachment_path else None,
        'filename': filename,
        'file_extension': file_extension,
        'subject': {
            'id': p.subject.id if p.subject else None,
            'name': p.subject.name if p.subject else None
        },
        'author': {
            'id': p.author.id if p.author else None,
            'username': p.author.username if p.author else None,
            'first_name': getattr(p.author, 'first_name', None),
            'last_name': getattr(p.author, 'last_name', None),
            'avatar_path': getattr(p.author, 'avatar_path', None),
            'get_full_name': f"{getattr(p.author, 'first_name', '')} {getattr(p.author, 'last_name', '')}".strip() or (p.author.username if p.author else '')
        },
        'comment_count': comment_count,
        'vote_value': vote_value
    }

    # comments
    comments_qs = Comment.objects.filter(post_id=post_id).select_related('author').order_by('created_at')
    comments = [
        {
            'id': c.id,
            'content': c.content,
            'created_at': c.created_at,
            'commenter': {
                'id': c.author.id if c.author else None,
                'username': c.author.username if c.author else None,
                'first_name': getattr(c.author, 'first_name', None),
                'last_name': getattr(c.author, 'last_name', None),
                'avatar_path': getattr(c.author, 'avatar_path', None),
                'get_full_name': f"{getattr(c.author, 'first_name', '')} {getattr(c.author, 'last_name', '')}".strip() if c.author else None
            }
        }
        for c in comments_qs
    ]

    # increment view count
    Post.objects.filter(pk=post_id).update(view_count=F('view_count') + 1)
    post['view_count'] += 1

    # related posts
    related_qs = Post.objects.filter(subject_id=post['subject']['id']).exclude(pk=post_id).select_related('author').order_by('-created_at')[:5]
    related_posts = [
        {
            'id': r.id,
            'title': r.title,
            'view_count': r.view_count,
            'created_at': r.created_at,
            'author': {
                'username': r.author.username if r.author else None,
                'get_full_name': f"{getattr(r.author, 'first_name', '')} {getattr(r.author, 'last_name', '')}".strip() or (r.author.username if r.author else None)
            }
        }
        for r in related_qs
    ]

    author_post_count = Post.objects.filter(author_id=post['author']['id']).count()
        
    context = {
        'is_authenticated': request.session.get('user_id') is not None,
        'username': request.session.get('username'),
        'post': post,
        'comments': comments,
        'related_posts': related_posts,
        'is_authenticated': request.session.get('user_id') is not None,
        'current_user_id': request.session.get('user_id'),
        'author_post_count': author_post_count
    }
    return render(request, 'forum/post_detail.html', context)


def add_comment(request, post_id):
    """Thêm bình luận"""
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập để bình luận')
        return redirect('accounts:login')
    
    if request.method != 'POST':
        return redirect('forum:post_detail', post_id=post_id)
    
    user_id = request.session['user_id']
    content = request.POST.get('content', '').strip()
    
    if not content:
        messages.error(request, 'Nội dung bình luận không được để trống')
        return redirect('forum:post_detail', post_id=post_id)
    
    if len(content) > 5000:
        messages.error(request, 'Bình luận quá dài (tối đa 5000 ký tự)')
        return redirect('forum:post_detail', post_id=post_id)
    
    try:
        # ensure post exists
        Post.objects.get(pk=post_id)
        from accounts.models import User
        commenter = None
        try:
            commenter = User.objects.get(pk=user_id)
        except Exception:
            commenter = None
        Comment.objects.create(content=content, author=commenter, post_id=post_id)
        messages.success(request, 'Bình luận đã được đăng!')
    except Post.DoesNotExist:
        raise Http404("Bài viết không tồn tại")
    except Exception as e:
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
    
    return redirect('forum:post_detail', post_id=post_id)


def delete_comment(request, comment_id):
    """Xóa bình luận"""
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']
    try:
        c = Comment.objects.get(pk=comment_id)
    except Comment.DoesNotExist:
        raise Http404("Bình luận không tồn tại")

    if not c.author or c.author.id != user_id:
        messages.error(request, 'Bạn không có quyền xóa bình luận này')
        return redirect('forum:post_detail', post_id=c.post_id)

    post_id = c.post_id
    c.delete()
    messages.success(request, 'Bình luận đã được xóa')
    return redirect('forum:post_detail', post_id=post_id)


def vote_post(request, post_id):
    """Vote cho bài viết (upvote = 1, downvote = -1)"""
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập để vote')
        return redirect('accounts:login')
    
    if request.method != 'POST':
        return redirect('forum:post_detail', post_id=post_id)
    
    user_id = request.session['user_id']
    vote_value = request.POST.get('vote_value')
    
    # Validate vote_value
    try:
        vote_value = int(vote_value)
        if vote_value not in (1, -1):
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, 'Giá trị vote không hợp lệ')
        return redirect('forum:post_detail', post_id=post_id)
    
    try:
        Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        raise Http404("Bài viết không tồn tại")

    from accounts.models import User
    voter = None
    try:
        voter = User.objects.get(pk=user_id)
    except Exception:
        voter = None

    existing_vote = Vote.objects.filter(voter_id=user_id, post_id=post_id).first()
    if existing_vote:
        if existing_vote.vote_value == vote_value:
            existing_vote.delete()
            messages.info(request, 'Đã hủy vote')
        else:
            existing_vote.vote_value = vote_value
            existing_vote.save()
            messages.success(request, 'Đã cập nhật vote')
    else:
        Vote.objects.create(vote_value=vote_value, voter=voter, post_id=post_id)
        messages.success(request, 'Đã vote thành công')
    
    
    return redirect('forum:post_detail', post_id=post_id)




def create_test(request, subject_id):
    """Tạo mới bài kiểm tra với câu hỏi"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')

    if request.method != 'POST':
        context = {
            'subject_id': subject_id,
            'username': request.session.get('username'),
            'is_authenticated': True,
        }
        return render(request, 'forum/create_test.html', context)

    user_id = request.session['user_id']
    title = request.POST.get('title')
    description = request.POST.get('description')
    time_limit = int(request.POST.get('time_limit', '0'))
    max_attempts = int(request.POST.get('max_attempts', '1'))
    selected_questions = request.POST.getlist('selected_questions')
        
    ends_at_str = request.POST.get('ends_at', '')
    ends_at = None
    if ends_at_str:
        try:
            ends_at = datetime.strptime(ends_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            messages.error(request, 'Định dạng ngày hết hạn không hợp lệ')
            return redirect('forum:create_test', subject_id=subject_id)

    try:
        # Create test via ORM
        author = None
        from accounts.models import User
        try:
            author = User.objects.get(pk=user_id)
        except Exception:
            author = None

        subject = None
        try:
            subject = Subject.objects.get(pk=subject_id)
        except Exception:
            subject = None

        t = Test.objects.create(
            title=title,
            description=description,
            time_limit=time_limit or None,
            ends_at=ends_at,
            subject=subject,
            author=author
        )

        # handle selected questions
        for i, question_data in enumerate(selected_questions):
            try:
                question = json.loads(question_data)
                if question.get('source') == 'new':
                    q = Question.objects.create(
                        content=question.get('content', ''),
                        subject=subject,
                        author=author
                    )

                    if question.get('type') == 'multiple_choice':
                        options = question.get('options', [])
                        correct_index = int(question.get('correct_answer_index', 0))
                        correct_option = None
                        for idx, opt in enumerate(options):
                            if opt and opt.strip():
                                opt_obj = MultipleChoiceOption.objects.create(content=opt.strip(), question=q)
                                if idx == correct_index:
                                    correct_option = opt_obj
                        if not correct_option:
                            messages.warning(request, f'Câu hỏi "{q.content[:50]}..." không có đáp án đúng hợp lệ')
                            q.delete()
                            continue
                        # create MultipleChoiceQuestion linking to Question safely
                        _create_with_relation(MultipleChoiceQuestion, q, {'correct_option': correct_option, 'randomize_options': bool(question.get('randomize_options', False))})
 
                    elif question.get('type') == 'essay':
                        # create EssayQuestion linking to Question safely
                        _create_with_relation(EssayQuestion, q, {'word_limit': int(question.get('word_limit', 0) or 0)})
                    question_obj = q
                else:
                    # existing question id
                    question_obj = Question.objects.get(pk=question.get('id'))

                TestQuestion.objects.create(test=t, question=question_obj, question_order=i)

            except Exception as e:
                messages.warning(request, f'Có lỗi khi thêm câu hỏi: {str(e)}')
                continue

        messages.success(request, 'Tạo bài kiểm tra thành công')
        return redirect('forum:test_detail', test_id=t.id)
    except Exception as e:
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        return redirect('forum:create_test', subject_id=subject_id)
    

def test_detail(request, test_id):
    """Chi tiết bài kiểm tra"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    try:
        t = Test.objects.get(pk=test_id)
    except Test.DoesNotExist:
        raise Http404("Bài kiểm tra không tồn tại")

    now = timezone.now()
    is_active = (t.ends_at is None) or (t.ends_at > now)

    # Normalize max_attempts: keep None to mean "unlimited", otherwise ensure an int
    raw_max_attempts = getattr(t, 'max_attempts', None)
    try:
        max_attempts_val = int(raw_max_attempts) if raw_max_attempts is not None else None
    except (ValueError, TypeError):
        max_attempts_val = None

    test = {
        'id': t.id,
        'title': t.title,
        'description': t.description,
        'time_limit': t.time_limit,
        'ends_at': t.ends_at,
        'created_at': t.created_at,
        # max_attempts_val is either int or None (None => unlimited)
        'max_attempts': max_attempts_val,
        'subject_id': t.subject.id if t.subject else None,
        'author_id': t.author.id if t.author else None,
        'is_active': is_active
    }

    user_id = request.session.get('user_id')
    if user_id:
        current_user_attempts = Submission.objects.filter(test_id=test_id, author_id=user_id).count()
    else:
        current_user_attempts = 0

    # Tính toán remaining attempts & progress an toàn khi max_attempts có thể là None
    if max_attempts_val is None:
        remaining_attempts = None   # None => không giới hạn
        progress_percent = 0
    else:
        # ensure non-negative remaining attempts
        remaining_attempts = max(0, int(max_attempts_val) - int(current_user_attempts))
        progress_percent = int((current_user_attempts / max_attempts_val) * 100) if max_attempts_val > 0 else 0

    context = {
        'test': test,
        'current_user_attempts': current_user_attempts,
        'remaining_attempts': remaining_attempts,
        'progress_percent': int(progress_percent),
        'is_authenticated': True,
        'username': request.session.get('username'),
        'is_author': user_id == test.get('author_id')
    }
    return render(request, 'forum/test_detail.html', context)


def create_question(request, subject_id):
    """Tạo câu hỏi mới"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    if request.method != 'POST':
        context = {
            'subject_id': subject_id,
            'is_authenticated': True,
            'username': request.session.get('username'),
        }
        return render(request, 'forum/create_question.html', context)

    user_id = request.session['user_id']
    question_type = request.POST.get('question_type')
    content = request.POST.get('content', '').strip()
    attachment = request.FILES.get('attachment')
    
    if not content:
        messages.error(request, 'Nội dung câu hỏi không được để trống')
        return redirect('forum:create_question', subject_id=subject_id)
    
    # Xử lý file đính kèm
    attachment_path = None
    if attachment:
        allowed_extensions = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']
        file_ext = attachment.name.split('.')[-1].lower()
        
        if file_ext not in allowed_extensions:
            messages.error(request, 'Định dạng file không hợp lệ')
            return redirect('forum:create_question', subject_id=subject_id)
        
        if attachment.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
            messages.error(request, 'File quá lớn (tối đa 25MB)')
            return redirect('forum:create_question', subject_id=subject_id)
        
        unique_name = f"{uuid.uuid4()}_{attachment.name}"
        upload_path = os.path.join('questions', unique_name)
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb+') as destination:
            for chunk in attachment.chunks():
                destination.write(chunk)
        
        attachment_path = upload_path
    
    # Create question via ORM
    try:
        from accounts.models import User
        author = None
        try:
            author = User.objects.get(pk=user_id)
        except Exception:
            author = None

        subject = None
        try:
            subject = Subject.objects.get(pk=subject_id)
        except Exception:
            subject = None

        q = Question.objects.create(content=content, attachment_path=attachment_path, subject=subject, author=author)

        if question_type == 'multiple_choice':
            options_json = request.POST.get('options_data')
            if not options_json:
                messages.error(request, 'Vui lòng thêm đáp án')
                q.delete()
                return redirect('forum:create_question', subject_id=subject_id)
            try:
                options_data = json.loads(options_json)
            except Exception:
                messages.error(request, 'Dữ liệu đáp án không hợp lệ')
                q.delete()
                return redirect('forum:create_question', subject_id=subject_id)

            if len(options_data) < 2:
                messages.error(request, 'Phải có ít nhất 2 đáp án')
                q.delete()
                return redirect('forum:create_question', subject_id=subject_id)

            correct_index = int(request.POST.get('correct_answer_index', -1))
            if correct_index < 0 or correct_index >= len(options_data):
                messages.error(request, 'Vui lòng chọn đáp án đúng')
                q.delete()
                return redirect('forum:create_question', subject_id=subject_id)

            correct_option = None
            for idx, option_text in enumerate(options_data):
                if not option_text.strip():
                    continue
                opt = MultipleChoiceOption.objects.create(content=option_text.strip(), question=q)
                if idx == correct_index:
                    correct_option = opt

            if not correct_option:
                messages.error(request, 'Đáp án đúng không hợp lệ')
                q.delete()
                return redirect('forum:create_question', subject_id=subject_id)

            # create MultipleChoiceQuestion for newly created Question safely
            _create_with_relation(MultipleChoiceQuestion, q, {'correct_option': correct_option, 'randomize_options': bool(request.POST.get('randomize_options'))})

        elif question_type == 'essay':
            # ensure word_limit is defined
            try:
                word_limit = int(request.POST.get('word_limit', 0))
            except (ValueError, TypeError):
                word_limit = 0
            _create_with_relation(EssayQuestion, q, {'word_limit': word_limit})

        messages.success(request, 'Tạo câu hỏi thành công')
        return redirect('forum:question_bank', subject_id=subject_id)
    except Exception as e:
        if attachment_path:
            try:
                os.remove(full_path)
            except:
                pass
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        return redirect('forum:create_question', subject_id=subject_id)


def take_test(request, test_id):
    """Làm bài kiểm tra trực tuyến"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']
    
    try:
        try:
            t = Test.objects.get(pk=test_id)
        except Test.DoesNotExist:
            messages.error(request, 'Bài kiểm tra không tồn tại')
            return redirect('forum:index')

        test_info = {
            'id': t.id,
            'title': t.title,
            'time_limit': t.time_limit or 60,
            'max_attempts': getattr(t, 'max_attempts', 1) or 1
        }

        attempt_count = Submission.objects.filter(test_id=test_id, author_id=user_id).count()
        if attempt_count >= test_info['max_attempts']:
            messages.error(request, 'Bạn đã vượt quá số lần nộp bài cho phép')
            return redirect('forum:test_detail', test_id=test_id)

        if request.method == 'POST':
            return handle_test_submission(request, test_id, user_id, attempt_count)

        return display_test(request, test_id, user_id, attempt_count, test_info)
    except Exception as e:
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        return redirect('forum:index')

def handle_test_submission(request, test_id, user_id, attempt_count):
    """Xử lý nộp bài - chấm tự động trắc nghiệm"""
    try:
        # Lấy thời gian làm bài từ POST request
        time_spent = int(request.POST.get('time_spent', 0))

        # Tạo đối tượng Submission mới
        submission = Submission.objects.create(
            test_id=test_id,
            author_id=user_id,
            attempt_number=attempt_count + 1,
            time_spent=time_spent
        )

        # Lấy danh sách các câu hỏi của bài test, với thông tin order
        tq_rows = list(TestQuestion.objects.filter(test_id=test_id).order_by('question_order').values_list('question_id', 'question_order'))
        question_ids = [qid for qid, _ in tq_rows if qid is not None]

        # Lấy tất cả câu hỏi có id trong question_ids
        questions = Question.objects.filter(id__in=question_ids)
        questions_map = {q.id: q for q in questions}  # Chuyển đổi danh sách câu hỏi thành dictionary để tra cứu nhanh

        # Lặp qua tất cả câu hỏi
        for qid, _order in tq_rows:
            q = questions_map.get(qid)  # Lấy câu hỏi từ map
            if not q:
                continue
            user_answer = request.POST.get(f'answer_{q.id}', '').strip()
            if not user_answer:
                continue

            # Use SQL-backed helpers to determine type
            mcq_meta = _get_mcq_meta(q.id)
            if mcq_meta:
                try:
                    selected_option_id = int(user_answer)
                except (ValueError, TypeError):
                    selected_option_id = None
                if selected_option_id:
                    ans = Answer.objects.create(submission=submission, question=q)
                    _create_with_relation(MultipleChoiceAnswer, ans, {'selected_option_id': selected_option_id})
                continue

            eq_meta = _get_essay_meta(q.id)
            if eq_meta:
                ans = Answer.objects.create(submission=submission, question=q)
                _create_with_relation(EssayAnswer, ans, {'content': user_answer, 'is_corrected': None})
                continue
 		
 	# Gửi thông báo thành công và chuyển hướng đến trang chi tiết submission
        messages.success(request, 'Nộp bài thành công!')
        return redirect('forum:submission_detail', submission_id=submission.id)

    except Exception as e:
        # Nếu có lỗi xảy ra, gửi thông báo lỗi và chuyển hướng đến trang làm bài
        messages.error(request, f'Có lỗi xảy ra: {str(e)}')
        return redirect('forum:take_test', test_id=test_id)

def display_test(request, test_id, user_id, attempt_count, test_info):
    """Hiển thị bài kiểm tra"""
    # Load TestQuestion rows (only question_id/question_order) and bulk-load related Question objects
    tq_rows = list(TestQuestion.objects.filter(test_id=test_id).order_by('question_order').values_list('question_id', 'question_order'))
    question_ids = [qid for qid, _ in tq_rows if qid is not None]
    questions_qs = Question.objects.filter(id__in=question_ids)
    questions_map = {q.id: q for q in questions_qs}

    questions = []
    for qid, _order in tq_rows:
        q = questions_map.get(qid)
        if not q:
            continue

        mcq_meta = _get_mcq_meta(q.id)
        eq_meta = _get_essay_meta(q.id)

        if mcq_meta:
            question_type = 'multiple_choice'
            randomize_options = bool(mcq_meta.get('randomize_options', False))
            word_limit = 0
        elif eq_meta:
            question_type = 'essay'
            randomize_options = False
            word_limit = int(eq_meta.get('word_limit', 0) or 0)
        else:
            question_type = 'unknown'
            randomize_options = False
            word_limit = 0

        question_data = {
             'id': q.id,
             'content': q.content,
             'type': question_type,
             'options': {},
             'randomize_options': randomize_options,
             'word_limit': word_limit
         }

        if question_type == 'multiple_choice':
            opts = list(MultipleChoiceOption.objects.filter(question_id=q.id).order_by('id'))
            option_list = [{'id': o.id, 'content': o.content} for o in opts]
            if randomize_options:
                import random
                random.shuffle(option_list)
            options = {}
            for idx, opt in enumerate(option_list):
                label = chr(65 + idx)
                options[label] = {'id': opt['id'], 'content': opt['content']}
            question_data['options'] = options

        questions.append(question_data)
     
    context = {
        'test': test_info,
        'test_id': test_id,
        'attempt_number': attempt_count + 1,
        'is_authenticated': True,
        'username': request.session.get('username'),
        'questions': questions,
    }
    
    return render(request, 'forum/take_test.html', context)


def question_bank(request, subject_id):
    """Ngân hàng câu hỏi"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    qs = Question.objects.filter(subject_id=subject_id).order_by('-created_at')
    questions = []
    for qobj in qs:
        # determine type using SQL-backed helpers instead of ORM reverse-access
        mcq_meta = _get_mcq_meta(qobj.id)
        eq_meta = _get_essay_meta(qobj.id)
        if mcq_meta:
            qtype = 'multiple_choice'
            correct_option_id = mcq_meta.get('correct_option_id')
            randomize = mcq_meta.get('randomize_options', False)
            word_limit = 0
        elif eq_meta:
            qtype = 'essay'
            correct_option_id = None
            randomize = 0
            word_limit = eq_meta.get('word_limit', 0)
        else:
            qtype = 'unknown'
            correct_option_id = None
            randomize = 0
            word_limit = 0

        question_data = {
            'id': qobj.id,
            'content': qobj.content,
            'created_at': qobj.created_at,
            'attachment_path': settings.MEDIA_URL + qobj.attachment_path if qobj.attachment_path else None,
            'type': qtype,
            'options': {},
            'correct_option_id': correct_option_id,
            'randomize_options': randomize,
            'word_limit': word_limit
        }

        if qtype == 'multiple_choice':
            opts = MultipleChoiceOption.objects.filter(question_id=qobj.id).order_by('id')
            options = {}
            for idx, opt in enumerate(opts):
                label = chr(65 + idx)
                options[label] = {'id': opt.id, 'content': opt.content, 'is_correct': (opt.id == correct_option_id)}
            question_data['options'] = options

        questions.append(question_data)
    
    context = {
        'subject_id': subject_id,
        'username': request.session.get('username'),
        'is_authenticated': True,
        'questions': questions,
    }
    return render(request, 'forum/question_bank.html', context)


def add_questions_to_test(request, test_id):
    """Thêm câu hỏi vào bài kiểm tra"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    try:
        t = Test.objects.get(pk=test_id)
    except Test.DoesNotExist:
        raise Http404("Bài kiểm tra không tồn tại")

    subject_id = t.subject.id if t.subject else None
    test_title = t.title
    author_id = t.author.id if t.author else None

    if author_id != request.session['user_id']:
        messages.error(request, 'Bạn không có quyền chỉnh sửa bài kiểm tra này')
        return redirect('forum:test_detail', test_id=test_id)

    # questions not yet in test
    existing_q_ids = list(TestQuestion.objects.filter(test_id=test_id).values_list('question_id', flat=True))
    qs = Question.objects.filter(subject_id=subject_id).exclude(id__in=existing_q_ids).order_by('-created_at')
    available_questions = []
    for qobj in qs:
        qtype = 'multiple_choice' if MultipleChoiceQuestion.objects.filter(id=qobj.id).exists() else ('essay' if EssayQuestion.objects.filter(id=qobj.id).exists() else 'unknown')
        question_data = {
            'id': qobj.id,
            'content': qobj.content,
            'type': qtype,
            'word_limit': EssayQuestion.objects.filter(id=qobj.id).values_list('word_limit', flat=True).first() or 0,
            'author_name': getattr(qobj.author, 'username', None) if hasattr(qobj, 'author') else None,
            'options': {}
        }
        if qtype == 'multiple_choice':
            correct_option_id = MultipleChoiceQuestion.objects.filter(id=qobj.id).values_list('correct_option_id', flat=True).first()
            opts = MultipleChoiceOption.objects.filter(question_id=qobj.id).order_by('id')
            options = {}
            for idx, opt in enumerate(opts):
                label = chr(65 + idx)
                options[label] = {'id': opt.id, 'content': opt.content, 'is_correct': (opt.id == correct_option_id)}
            question_data['options'] = options
        available_questions.append(question_data)
    
    if request.method == 'POST':
        selected_questions = request.POST.getlist('question_ids')

        if not selected_questions:
            messages.error(request, 'Vui lòng chọn ít nhất một câu hỏi')
            return redirect('forum:add_questions_to_test', test_id=test_id)

        try:
            # compute starting order
            current_max = TestQuestion.objects.filter(test_id=test_id).aggregate(max_order=Sum('question_order'))
            # If no entries, start -1 -> then +1 gives 0
            max_order = -1
            existing = TestQuestion.objects.filter(test_id=test_id).values_list('question_order', flat=True)
            if existing:
                max_order = max(existing)

            for i, question_id in enumerate(selected_questions):
                TestQuestion.objects.create(test_id=test_id, question_id=int(question_id), question_order=max_order + i + 1)

            messages.success(request, f'Đã thêm {len(selected_questions)} câu hỏi vào bài kiểm tra')
            return redirect('forum:test_detail', test_id=test_id)
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra: {str(e)}')
            return redirect('forum:add_questions_to_test', test_id=test_id)
    
    context = {
        'test_id': test_id,
        'test_title': test_title,
        'subject_id': subject_id,
        'username': request.session.get('username'),
        'is_authenticated': True,
        'available_questions': available_questions,
    }
    return render(request, 'forum/add_questions_to_test.html', context)

def submissions_history(request, test_id):
    """Lịch sử nộp bài"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']
    # Use ORM to fetch test and submissions
    try:
        test = Test.objects.get(pk=test_id)
    except Test.DoesNotExist:
        raise Http404("Bài kiểm tra không tồn tại")
    test_title = test.title
    is_test_author = (test.author.id == user_id)

    if is_test_author:
        subs_qs = Submission.objects.filter(test_id=test_id).order_by('-created_at')
    else:
        subs_qs = Submission.objects.filter(test_id=test_id, author_id=user_id).order_by('-created_at')

    submissions = []
    for s in subs_qs:
        answers_qs = Answer.objects.filter(submission_id=s.id).select_related('question')
        total_questions = answers_qs.count()
        total_score = 0
        for a in answers_qs:
            qid = a.question_id
            if MultipleChoiceQuestion.objects.filter(id=qid).exists():
                mcq = MultipleChoiceQuestion.objects.get(id=qid)
                sel = MultipleChoiceAnswer.objects.filter(id=a.id).values_list('selected_option_id', flat=True).first()
                if sel is not None and mcq.correct_option_id == sel:
                    total_score += 1
            elif EssayQuestion.objects.filter(id=qid).exists():
                is_corr = EssayAnswer.objects.filter(id=a.id).values_list('is_corrected', flat=True).first()
                if is_corr:
                    total_score += 1

        submissions.append({
            'id': s.id,
            'created_at': s.created_at,
            'time_spent': s.time_spent,
            'attempt_number': s.attempt_number,
            'total_score': int(total_score),
            'max_score': total_questions
        })
    
    context = {
        'is_authenticated': True,
        'username': request.session.get('username'),
        'submissions': submissions,
        'test_id': test_id,
        'test_title': test_title,
    }
    return render(request, 'forum/submissions_history.html', context)


def submission_detail(request, submission_id):
    """Chi tiết bài nộp"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    try:
        submission = Submission.objects.select_related('test').get(pk=submission_id)
    except Submission.DoesNotExist:
        raise Http404("Bài nộp không tồn tại")

    answers_qs = Answer.objects.filter(submission_id=submission_id).select_related('question').order_by('id')
    answers = []
    total_score = 0
    total_questions = 0

    for a in answers_qs:
        q = a.question
        question_type = 'unknown'
        score = None
        answer_content = ''
        is_correct = False
        correct_answer_text = ''

        if MultipleChoiceQuestion.objects.filter(id=q.id).exists():
            question_type = 'multiple_choice'
            mcq = MultipleChoiceQuestion.objects.get(id=q.id)
            selected_option_id = MultipleChoiceAnswer.objects.filter(id=a.id).values_list('selected_option_id', flat=True).first()

            opts = MultipleChoiceOption.objects.filter(question_id=q.id).order_by('id')
            for idx, opt in enumerate(opts):
                label = chr(65 + idx)
                if opt.id == selected_option_id:
                    user_answer_text = f"{label}. {opt.content}"
                if getattr(mcq, 'correct_option_id', None) == opt.id:
                    correct_answer_text = f"{label}. {opt.content}"

            is_correct = (selected_option_id == getattr(mcq, 'correct_option_id', None))
            score = 1 if is_correct else 0
            answer_content = user_answer_text if 'user_answer_text' in locals() else ''
            total_score += score
            total_questions += 1

        elif EssayQuestion.objects.filter(id=q.id).exists():
            question_type = 'essay'
            ea = EssayAnswer.objects.filter(id=a.id).first()
            answer_content = ea.content if ea else ''
            is_corrected = ea.is_corrected if ea else None
            if is_corrected is not None:
                score = 1 if is_corrected else 0
                total_score += score
                total_questions += 1
            else:
                score = None
                total_questions += 1

        answers.append({
            'id': a.id,
            'question_id': q.id,
            'question_content': q.content,
            'question_type': question_type,
            'answer_content': answer_content,
            'score': score,
            'is_correct': is_correct,
            'correct_answer': correct_answer_text,
            'is_corrected': getattr(ea, 'is_corrected', None) if question_type == 'essay' else True
        })

    is_test_author = (submission.test.author.id == request.session.get('user_id'))

    context = {
        'username': request.session.get('username'),
        'is_authenticated': True,
        'is_test_author': is_test_author,
        'submission': {
            'id': submission.id,
            'created_at': submission.created_at,
            'time_spent': submission.time_spent,
            'attempt_number': submission.attempt_number,
            'test_id': submission.test.id,
            'author_id': submission.author.id,
            'test_title': submission.test.title,
            'total_score': total_score,
            'max_score': total_questions
        },
        'answers': answers,
        'total_questions': total_questions
    }
    return render(request, 'forum/submission_detail.html', context)


def grade_submission(request, submission_id):
    """Chấm điểm bài nộp (chỉ tác giả bài kiểm tra)"""
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    user_id = request.session['user_id']
    try:
        submission = Submission.objects.select_related('test', 'author').get(pk=submission_id)
    except Submission.DoesNotExist:
        raise Http404("Bài nộp không tồn tại")

    test_id = submission.test.id
    test_title = submission.test.title
    test_author_id = submission.test.author.id
    student_id = submission.author.id

    if test_author_id != user_id:
        messages.error(request, 'Bạn không có quyền chấm bài này')
        return redirect('forum:submission_detail', submission_id=submission_id)

    if request.method == 'POST':
        try:
            for key, value in request.POST.items():
                if key.startswith('grade_'):
                    answer_id = int(key.split('_')[1])
                    is_correct = int(value)  # 1 = đúng, 0 = sai
                    EssayAnswer.objects.filter(id=answer_id).update(is_corrected=bool(is_correct))

            messages.success(request, 'Đã chấm bài thành công!')
            return redirect('forum:submission_detail', submission_id=submission_id)
        except Exception as e:
            messages.error(request, f'Lỗi khi chấm bài: {str(e)}')

    # Lấy danh sách câu hỏi tự luận
    essay_answers = []
    answers_qs = Answer.objects.filter(submission_id=submission_id, question__essayquestion__isnull=False).order_by('id').select_related('question')
    for a in answers_qs:
        eq = None
        try:
            eq = a.question.essayquestion
        except Exception:
            eq = None
        ea = EssayAnswer.objects.filter(id=a.id).first()
        essay_answers.append({
            'answer_id': a.id,
            'question_content': a.question.content,
            'answer_content': ea.content if ea else '',
            'is_corrected': ea.is_corrected if ea else None,
            'word_limit': getattr(eq, 'word_limit', 0)
        })

    student = submission.author
    student_name = f"{getattr(student, 'first_name', '')} {getattr(student, 'last_name', '')}".strip() or getattr(student, 'username', '')
    
    context = {
        'is_authenticated': True,
        'username': request.session.get('username'),
        'submission_id': submission_id,
        'test_title': test_title,
        'student_name': student_name,
        'essay_answers': essay_answers
    }
    
    return render(request, 'forum/grade_submission.html', context)
