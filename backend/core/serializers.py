"""
Serializers for core models.
"""
from rest_framework import serializers
from core.models import (
    User, College, Department, Teacher, Subject, Section,
    Classroom, SubjectTeacherMapping, Timetable, TeacherPreference
)


class CollegeSerializer(serializers.ModelSerializer):
    """Serializer for College model."""
    class Meta:
        model = College
        fields = ['id', 'name', 'code', 'logo', 'domain', 'subdomain', 
                 'address', 'phone', 'email', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    full_name = serializers.ReadOnlyField()
    college_name = serializers.CharField(source='college.name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 
                 'role', 'college', 'college_name', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model."""
    college_name = serializers.CharField(source='college.name', read_only=True)
    hod_name = serializers.CharField(source='hod.full_name', read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'college', 'college_name', 'name', 'code', 'hod', 'hod_name', 'created_at']
        read_only_fields = ['id', 'created_at', 'college']


class TeacherSerializer(serializers.ModelSerializer):
    """Serializer for Teacher model."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Teacher
        fields = ['id', 'user', 'user_email', 'user_name', 'employee_id', 
                 'department', 'department_name', 'designation', 'max_weekly_hours', 'created_at']
        read_only_fields = ['id', 'created_at']


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject model."""
    college_name = serializers.CharField(source='college.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Subject
        fields = ['id', 'college', 'college_name', 'code', 'name', 'credits', 
                 'weekly_quota', 'is_lab', 'department', 'department_name', 'created_at']
        read_only_fields = ['id', 'created_at', 'college']


class SectionSerializer(serializers.ModelSerializer):
    """Serializer for Section model."""
    college_name = serializers.CharField(source='college.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Section
        fields = ['id', 'college', 'college_name', 'name', 'student_strength', 
                 'department', 'department_name', 'year', 'semester', 'created_at']
        read_only_fields = ['id', 'created_at', 'college']


class ClassroomSerializer(serializers.ModelSerializer):
    """Serializer for Classroom model."""
    college_name = serializers.CharField(source='college.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Classroom
        fields = ['id', 'college', 'college_name', 'name', 'capacity', 
                 'is_lab', 'department', 'department_name', 'created_at']
        read_only_fields = ['id', 'created_at', 'college']


class SubjectTeacherMappingSerializer(serializers.ModelSerializer):
    """Serializer for SubjectTeacherMapping model."""
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.full_name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)
    
    class Meta:
        model = SubjectTeacherMapping
        fields = ['id', 'subject', 'subject_code', 'subject_name', 'teacher', 
                 'teacher_name', 'section', 'section_name', 'is_primary', 'created_at']
        read_only_fields = ['id', 'created_at']


class TimetableSerializer(serializers.ModelSerializer):
    """Serializer for Timetable model."""
    college_name = serializers.CharField(source='college.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Timetable
        fields = ['id', 'college', 'college_name', 'name', 'academic_year', 
                 'semester', 'status', 'timetable_data', 'fitness_score', 
                 'generation_config', 'created_by', 'created_by_name', 
                 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'fitness_score', 'college']


class TeacherPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for TeacherPreference model."""
    teacher_name = serializers.CharField(source='teacher.user.full_name', read_only=True)
    
    class Meta:
        model = TeacherPreference
        fields = ['id', 'teacher', 'teacher_name', 'preferred_time_slots', 
                 'preferred_days', 'unavailable_slots', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class GenerateTimetableSerializer(serializers.Serializer):
    """Serializer for timetable generation request."""
    name = serializers.CharField(max_length=255)
    academic_year = serializers.CharField(max_length=20)
    semester = serializers.CharField(max_length=20, required=False, allow_blank=True)
    total_generations = serializers.IntegerField(default=50, min_value=1, max_value=200)
    
    # Optional overrides
    time_slots = serializers.DictField(required=False)
    day_map = serializers.DictField(required=False)
    time_slot_map = serializers.DictField(required=False)
    working_days = serializers.ListField(child=serializers.CharField(), required=False)
    fixed_teacher_assignment = serializers.DictField(required=False)
