from django.db import models


class User(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    avatar_path = models.CharField(max_length=512, blank=True, null=True)

    # Wallet related fields
    coins = models.IntegerField(default=0)
    last_checkin = models.DateField(blank=True, null=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.username or f'user-{self.id}'


class Department(models.Model):
    name = models.CharField(max_length=200)

    class Meta:
        db_table = 'departments'

    def __str__(self):
        return self.name


class Major(models.Model):
    name = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)

    class Meta:
        db_table = 'majors'

    def __str__(self):
        return self.name


class Student(models.Model):
    id = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, db_column='id')
    student_code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    enrollment_year = models.IntegerField(blank=True, null=True)
    major = models.ForeignKey(Major, on_delete=models.SET_NULL, blank=True, null=True)
    wallet_address = models.CharField(max_length=64, blank=True, null=True)
    encrypted_private_key = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'students'


class Teacher(models.Model):
    id = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, db_column='id')
    teacher_code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    degree = models.CharField(max_length=200, blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        db_table = 'teachers'


class Referral(models.Model):
    referrer = models.ForeignKey(User, related_name='referrals_made', on_delete=models.CASCADE)
    referred = models.ForeignKey(User, related_name='referral_record', on_delete=models.CASCADE)
    rewarded_referrer = models.BooleanField(default=False)
    rewarded_referred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'referrals'
