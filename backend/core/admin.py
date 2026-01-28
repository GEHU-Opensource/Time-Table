"""
Django admin configuration.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from core.models import (
    User, College, Department, Teacher, Subject, Section,
    Classroom, SubjectTeacherMapping, Timetable, TeacherPreference
)


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'subdomain', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'subdomain']
    readonly_fields = ['id', 'created_at', 'updated_at']


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from core.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ('email',)

    list_display = ('email', 'full_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'role', 'college')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'role', 'college'),
        }),
    )

    filter_horizontal = ('groups', 'user_permissions')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'college', 'hod', 'created_at']
    list_filter = ['college', 'created_at']
    search_fields = ['name', 'code']


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['user', 'employee_id', 'department', 'designation', 'max_weekly_hours']
    list_filter = ['department', 'designation']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'employee_id']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'college', 'credits', 'weekly_quota', 'is_lab']
    list_filter = ['college', 'is_lab', 'department']
    search_fields = ['code', 'name']


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'college', 'student_strength', 'year', 'semester']
    list_filter = ['college', 'year', 'semester']
    search_fields = ['name']


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ['name', 'college', 'capacity', 'is_lab']
    list_filter = ['college', 'is_lab']
    search_fields = ['name']


@admin.register(SubjectTeacherMapping)
class SubjectTeacherMappingAdmin(admin.ModelAdmin):
    list_display = ['subject', 'teacher', 'section', 'is_primary']
    list_filter = ['is_primary', 'subject__college']
    search_fields = ['subject__code', 'teacher__user__email']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['name', 'college', 'academic_year', 'status', 'fitness_score', 'created_at']
    list_filter = ['status', 'college', 'created_at']
    search_fields = ['name', 'academic_year']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(TeacherPreference)
class TeacherPreferenceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'created_at', 'updated_at']
    search_fields = ['teacher__user__email']
