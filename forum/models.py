from django.db import models
from accounts.models import User


class Subject(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'subjects'

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=500)
    content = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    attachment_path = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    view_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'posts'

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    # Legacy DB column is `commenter_id` — map the ORM field `author` to that column
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, db_column='commenter_id')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'comments'


class Vote(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    voter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    vote_value = models.IntegerField(default=0)

    class Meta:
        db_table = 'votes'


class Test(models.Model):
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    time_limit = models.IntegerField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'tests'


class Question(models.Model):
    content = models.TextField()
    attachment_path = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    class Meta:
        db_table = 'questions'


# The legacy `test_questions` table uses a composite primary key (test_id, question_id)
# which Django ORM does not support. We keep a lightweight mapping model for
# convenience but mark it unmanaged so Django won't expect an `id` column or try
# to create migrations for it. Use raw SQL for inserts/queries against
# `test_questions` when preserving existing data.

class TestQuestion(models.Model):
    test_id = models.IntegerField()
    question_id = models.IntegerField()
    question_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'test_questions'
        managed = False


class EssayQuestion(models.Model):
    id = models.OneToOneField(Question, on_delete=models.CASCADE, primary_key=True)
    word_limit = models.IntegerField(default=0)

    class Meta:
        db_table = 'essay_questions'


class MultipleChoiceOption(models.Model):
    content = models.TextField()
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')

    class Meta:
        db_table = 'multiple_choice_options'


class MultipleChoiceQuestion(models.Model):
    id = models.OneToOneField(Question, on_delete=models.CASCADE, primary_key=True)
    correct_option = models.OneToOneField(MultipleChoiceOption, on_delete=models.CASCADE)
    randomize_options = models.BooleanField(default=True)

    class Meta:
        db_table = 'multiple_choice_questions'


class Submission(models.Model):
    time_spent = models.IntegerField()
    attempt_number = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'submissions'


class Answer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    class Meta:
        db_table = 'answers'


class MultipleChoiceAnswer(models.Model):
    id = models.OneToOneField(Answer, on_delete=models.CASCADE, primary_key=True)
    selected_option = models.ForeignKey(MultipleChoiceOption, on_delete=models.CASCADE)

    class Meta:
        db_table = 'multiple_choice_answers'


class EssayAnswer(models.Model):
    id = models.OneToOneField(Answer, on_delete=models.CASCADE, primary_key=True)
    content = models.TextField(blank=True, null=True)
    is_corrected = models.BooleanField(null=True)

    class Meta:
        db_table = 'essay_answers'
