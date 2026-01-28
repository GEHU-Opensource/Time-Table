"""
Management command to load sample data for demonstration.
"""
from django.core.management.base import BaseCommand
from core.models import (
    College, User, Department, Teacher, Subject, Section,
    Classroom, SubjectTeacherMapping, TeacherPreference
)
from algorithm.helpers import initialize_teacher_availability


class Command(BaseCommand):
    help = 'Load sample data for demonstration'

    def handle(self, *args, **options):
        self.stdout.write('Loading sample data...')

        # Create or get master admin
        master_admin, created = User.objects.get_or_create(
            email='ayushkapri18@gmail.com',
            defaults={
                'first_name': 'Ayush',
                'last_name': 'Kapri',
                'role': User.Role.MASTER_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            master_admin.set_password('admin123')
            master_admin.save()
            self.stdout.write(self.style.SUCCESS('Created master admin (admin@timetable.com / admin123)'))

        # Create sample college
        college, created = College.objects.get_or_create(
            code='GEHU',
            defaults={
                'name': 'Graphic Era',
                'subdomain': 'graphicera',
                'email': 'info@gehu.ac.in',
                'phone': '+91XXXXXXXXXX',
                'address': 'Graphic Era Hill University, India',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created college: {college.name}'))

        # Create college admin
        college_admin, created = User.objects.get_or_create(
            email='admin@democollege.com',
            defaults={
                'first_name': 'College',
                'last_name': 'Admin',
                'role': User.Role.COLLEGE_ADMIN,
                'college': college,
            }
        )
        if created:
            college_admin.set_password('admin123')
            college_admin.save()
            self.stdout.write(self.style.SUCCESS('Created college admin (admin@democollege.com / admin123)'))

        # Create department
        dept, created = Department.objects.get_or_create(
            college=college,
            code='CS',
            defaults={
                'name': 'Computer Science',
                'hod': None,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created department: {dept.name}'))

        # Create teachers
        teachers_data = [
            {'email': 'teacher1@demo.com', 'name': 'John', 'surname': 'Doe', 'emp_id': 'T001', 'designation': 'Professor'},
            {'email': 'teacher2@demo.com', 'name': 'Jane', 'surname': 'Smith', 'emp_id': 'T002', 'designation': 'Associate Professor'},
            {'email': 'teacher3@demo.com', 'name': 'Bob', 'surname': 'Johnson', 'emp_id': 'T003', 'designation': 'Assistant Professor'},
            {'email': 'teacher4@demo.com', 'name': 'Alice', 'surname': 'Williams', 'emp_id': 'T004', 'designation': 'Professor'},
        ]

        teachers = []
        for t_data in teachers_data:
            user, created = User.objects.get_or_create(
                email=t_data['email'],
                defaults={
                    'first_name': t_data['name'],
                    'last_name': t_data['surname'],
                    'role': User.Role.FACULTY,
                    'college': college,
                }
            )
            if created:
                user.set_password('teacher123')
                user.save()

            teacher, created = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': t_data['emp_id'],
                    'department': dept,
                    'designation': t_data['designation'],
                    'max_weekly_hours': 20,
                }
            )
            teachers.append(teacher)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created teacher: {user.full_name}'))

        # Create subjects
        subjects_data = [
            {'code': 'CS101', 'name': 'Introduction to Programming', 'credits': 3, 'quota': 3, 'is_lab': False},
            {'code': 'CS102', 'name': 'Data Structures', 'credits': 4, 'quota': 4, 'is_lab': False},
            {'code': 'CS103', 'name': 'Database Systems', 'credits': 3, 'quota': 3, 'is_lab': False},
            {'code': 'CS104', 'name': 'Programming Lab', 'credits': 2, 'quota': 2, 'is_lab': True},
            {'code': 'CS105', 'name': 'Web Development', 'credits': 3, 'quota': 3, 'is_lab': False},
        ]

        subjects = []
        for s_data in subjects_data:
            subject, created = Subject.objects.get_or_create(
                college=college,
                code=s_data['code'],
                defaults={
                    'name': s_data['name'],
                    'credits': s_data['credits'],
                    'weekly_quota': s_data['quota'],
                    'is_lab': s_data['is_lab'],
                    'department': dept,
                }
            )
            subjects.append(subject)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created subject: {subject.code}'))

        # Create sections
        sections_data = [
            {'name': 'A', 'strength': 60},
            {'name': 'B', 'strength': 60},
            {'name': 'C', 'strength': 50},
        ]

        sections = []
        for s_data in sections_data:
            section, created = Section.objects.get_or_create(
                college=college,
                name=s_data['name'],
                year=1,
                semester=1,
                defaults={
                    'student_strength': s_data['strength'],
                    'department': dept,
                }
            )
            sections.append(section)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created section: {section.name}'))

        # Create classrooms
        classrooms_data = [
            {'name': 'R101', 'capacity': 80, 'is_lab': False},
            {'name': 'R102', 'capacity': 80, 'is_lab': False},
            {'name': 'R103', 'capacity': 60, 'is_lab': False},
            {'name': 'L101', 'capacity': 40, 'is_lab': True},
            {'name': 'L102', 'capacity': 40, 'is_lab': True},
        ]

        classrooms = []
        for c_data in classrooms_data:
            classroom, created = Classroom.objects.get_or_create(
                college=college,
                name=c_data['name'],
                defaults={
                    'capacity': c_data['capacity'],
                    'is_lab': c_data['is_lab'],
                    'department': dept,
                }
            )
            classrooms.append(classroom)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created classroom: {classroom.name}'))

        # Create subject-teacher mappings
        mappings = [
            (subjects[0], teachers[0], sections[0]),  # CS101 -> T001 -> Section A
            (subjects[0], teachers[0], sections[1]),  # CS101 -> T001 -> Section B
            (subjects[1], teachers[1], sections[0]),  # CS102 -> T002 -> Section A
            (subjects[1], teachers[1], sections[1]),  # CS102 -> T002 -> Section B
            (subjects[2], teachers[2], sections[0]),  # CS103 -> T003 -> Section A
            (subjects[3], teachers[0], sections[0]),  # CS104 -> T001 -> Section A
            (subjects[4], teachers[3], sections[1]),  # CS105 -> T004 -> Section B
        ]

        for subject, teacher, section in mappings:
            mapping, created = SubjectTeacherMapping.objects.get_or_create(
                subject=subject,
                teacher=teacher,
                section=section,
                defaults={'is_primary': True}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created mapping: {subject.code} -> {teacher.employee_id} -> {section.name}'
                    )
                )

        # Create teacher preferences
        for teacher in teachers:
            pref, created = TeacherPreference.objects.get_or_create(
                teacher=teacher,
                defaults={
                    'preferred_time_slots': [1, 2, 3, 4],  # Morning slots
                    'preferred_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday'],
                    'unavailable_slots': [],
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created preferences for {teacher.user.full_name}')
                )

        self.stdout.write(self.style.SUCCESS('\nSample data loaded successfully!'))
        self.stdout.write(self.style.SUCCESS('\nLogin credentials:'))
        self.stdout.write(self.style.SUCCESS('Master Admin: ayushkapri18@gmail.com / admin123'))
        self.stdout.write(self.style.SUCCESS('College Admin: admin@democollege.com / admin123'))
        self.stdout.write(self.style.SUCCESS('Teachers: teacher1@demo.com / teacher123 (and similar)'))
