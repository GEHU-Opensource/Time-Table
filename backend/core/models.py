"""
Core models for multi-tenant timetable management system.
"""
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    """Custom user manager."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.MASTER_ADMIN)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class College(models.Model):
    """College/Institution model for multi-tenancy."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    logo = models.ImageField(upload_to='colleges/logos/', null=True, blank=True)
    domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    subdomain = models.CharField(max_length=100, unique=True, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'colleges'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with role-based access."""
    
    class Role(models.TextChoices):
        MASTER_ADMIN = 'master_admin', 'Master Admin'
        COLLEGE_ADMIN = 'college_admin', 'College Admin'
        HOD = 'hod', 'Head of Department'
        FACULTY = 'faculty', 'Faculty'
        STUDENT = 'student', 'Student'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FACULTY)
    college = models.ForeignKey(College, on_delete=models.CASCADE, null=True, blank=True, related_name='users')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.email} ({self.role})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Department(models.Model):
    """Department model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)
    hod = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='departments_headed')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'departments'
        unique_together = ['college', 'code']
    
    def __str__(self):
        return f"{self.name} ({self.college.name})"


class Teacher(models.Model):
    """Teacher/Faculty model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=50)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='teachers')
    designation = models.CharField(max_length=100)
    max_weekly_hours = models.IntegerField(default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'teachers'
        unique_together = ['department', 'employee_id']
    
    def __str__(self):
        return f"{self.user.full_name} ({self.employee_id})"


class Subject(models.Model):
    """Subject/Course model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='subjects')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    credits = models.IntegerField()
    weekly_quota = models.IntegerField()  # Number of classes per week
    is_lab = models.BooleanField(default=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subjects'
        unique_together = ['college', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Section(models.Model):
    """Section/Class model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=50)  # e.g., "A", "B", "C"
    student_strength = models.IntegerField()
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='sections', null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    semester = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sections'
        unique_together = ['college', 'name', 'year', 'semester']
    
    def __str__(self):
        return f"{self.name} ({self.college.name})"


class Classroom(models.Model):
    """Classroom model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='classrooms')
    name = models.CharField(max_length=100)
    capacity = models.IntegerField()
    is_lab = models.BooleanField(default=False)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='classrooms')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'classrooms'
        unique_together = ['college', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.college.name})"


class SubjectTeacherMapping(models.Model):
    """Mapping between subjects and teachers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_mappings')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='subject_mappings')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='subject_teacher_mappings', null=True, blank=True)
    is_primary = models.BooleanField(default=True)  # Primary teacher for this subject
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'subject_teacher_mappings'
        unique_together = ['subject', 'teacher', 'section']
    
    def __str__(self):
        return f"{self.subject.code} - {self.teacher.user.full_name}"


class Timetable(models.Model):
    """Generated timetable model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name='timetables')
    name = models.CharField(max_length=255)
    academic_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ], default='draft')
    timetable_data = models.JSONField()  # Stores the generated timetable
    fitness_score = models.FloatField(null=True, blank=True)
    generation_config = models.JSONField(null=True, blank=True)  # Stores algorithm config
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_timetables')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetables'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.college.name})"


class TeacherPreference(models.Model):
    """Teacher preferences for time slots."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='preferences')
    preferred_time_slots = models.JSONField(default=list)  # List of preferred time slot IDs
    preferred_days = models.JSONField(default=list)  # List of preferred days
    unavailable_slots = models.JSONField(default=list)  # List of unavailable time slots
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teacher_preferences'
    
    def __str__(self):
        return f"Preferences for {self.teacher.user.full_name}"
