"""
Views for core models.
"""
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from core.models import (
    College, Department, Teacher, Subject, Section,
    Classroom, SubjectTeacherMapping, Timetable, TeacherPreference
)
from core.serializers import (
    CollegeSerializer, DepartmentSerializer, TeacherSerializer,
    SubjectSerializer, SectionSerializer, ClassroomSerializer,
    SubjectTeacherMappingSerializer, TimetableSerializer,
    TeacherPreferenceSerializer, GenerateTimetableSerializer
)
from core.permissions import (
    IsMasterAdmin, IsCollegeAdminOrMaster, IsCollegeMember, IsOwnerOrAdmin
)
from algorithm import run_timetable_generation
from algorithm.helpers import initialize_teacher_availability
import logging

logger = logging.getLogger(__name__)


class CollegeViewSet(viewsets.ModelViewSet):
    """ViewSet for College management."""
    queryset = College.objects.all()
    serializer_class = CollegeSerializer
    permission_classes = [IsAuthenticated, IsMasterAdmin]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code', 'subdomain']


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Department management."""
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return Department.objects.all()
        return Department.objects.filter(college=user.college)
    
    def perform_create(self, serializer):
        if not self.request.user.college:
            raise ValidationError("User has no college assigned")

        serializer.save(college=self.request.user.college)


class TeacherViewSet(viewsets.ModelViewSet):
    """ViewSet for Teacher management."""
    serializer_class = TeacherSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'employee_id']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return Teacher.objects.all()
        return Teacher.objects.filter(department__college=user.college)


class SubjectViewSet(viewsets.ModelViewSet):
    """ViewSet for Subject management."""
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    search_fields = ['code', 'name']
    filterset_fields = ['is_lab', 'department']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return Subject.objects.all()
        return Subject.objects.filter(college=user.college)
    
    def perform_create(self, serializer):

        if not self.request.user.college:
            raise ValidationError("User has no college assigned")
        serializer.save(college=self.request.user.college)


class SectionViewSet(viewsets.ModelViewSet):
    """ViewSet for Section management."""
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    filterset_fields = ['year', 'semester']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return Section.objects.all()
        return Section.objects.filter(college=user.college)
    
    def perform_create(self, serializer):
        if not self.request.user.college:
            raise ValidationError("User has no college assigned")
        serializer.save(college=self.request.user.college)


class ClassroomViewSet(viewsets.ModelViewSet):
    """ViewSet for Classroom management."""
    serializer_class = ClassroomSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    filterset_fields = ['is_lab']
    search_fields = ['name']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return Classroom.objects.all()
        return Classroom.objects.filter(college=user.college)
    
    def perform_create(self, serializer):
        if not self.request.user.college:
            raise ValidationError("User has no college assigned")
        serializer.save(college=self.request.user.college)


class SubjectTeacherMappingViewSet(viewsets.ModelViewSet):
    """ViewSet for Subject-Teacher mapping."""
    serializer_class = SubjectTeacherMappingSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    filterset_fields = ['is_primary', 'subject', 'teacher', 'section']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return SubjectTeacherMapping.objects.all()
        return SubjectTeacherMapping.objects.filter(
            subject__college=user.college
        )


class TeacherPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for Teacher Preference management."""
    serializer_class = TeacherPreferenceSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return TeacherPreference.objects.all()
        return TeacherPreference.objects.filter(
            teacher__department__college=user.college
        )


class TimetableViewSet(viewsets.ModelViewSet):
    """ViewSet for Timetable management."""
    serializer_class = TimetableSerializer
    permission_classes = [IsAuthenticated, IsCollegeMember]
    filterset_fields = ['status', 'academic_year', 'semester']
    search_fields = ['name', 'academic_year']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'master_admin':
            return Timetable.objects.all()
        return Timetable.objects.filter(college=user.college)
    
    def perform_create(self, serializer):
        if not self.request.user.college:
            raise ValidationError("User has no college assigned")

        serializer.save(
            college=self.request.user.college,
            created_by=self.request.user
        )


class GenerateTimetableViewSet(viewsets.ViewSet):
    """ViewSet for generating timetables."""
    permission_classes = [IsAuthenticated, IsCollegeAdminOrMaster]
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a timetable using the genetic algorithm."""
        serializer = GenerateTimetableSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        college = request.user.college
        if not college:
            return Response(
                {'error': 'User must be associated with a college'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get all required data from database
            sections = Section.objects.filter(college=college)
            classrooms = Classroom.objects.filter(college=college, is_lab=False)
            labs = Classroom.objects.filter(college=college, is_lab=True)
            subjects = Subject.objects.filter(college=college)
            teachers = Teacher.objects.filter(department__college=college)
            mappings = SubjectTeacherMapping.objects.filter(subject__college=college)
            
            # Validate resources exist
            if not sections.exists():
                return Response(
                    {'error': 'No sections found. Please add sections first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not teachers.exists():
                return Response(
                    {'error': 'No teachers found. Please add teachers first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not subjects.exists():
                return Response(
                    {'error': 'No subjects found. Please add subjects first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not classrooms.exists() and not labs.exists():
                return Response(
                    {'error': 'No classrooms or labs found. Please add classrooms/labs first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not mappings.exists():
                return Response(
                    {'error': 'No subject-teacher mappings found. Please create mappings first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Build data structures for algorithm
            total_sections = {s.name: s.student_strength for s in sections}
            total_classrooms = {c.name: c.capacity for c in classrooms}
            total_labs = {l.name: l.capacity for l in labs}
            
            # Build teacher-subject mapping
            teacher_subject_mapping = {}
            for mapping in mappings:
                subject_code = mapping.subject.code
                teacher_id = mapping.teacher.employee_id
                if subject_code not in teacher_subject_mapping:
                    teacher_subject_mapping[subject_code] = []
                teacher_subject_mapping[subject_code].append(teacher_id)
            
            # Build subject quota limits
            subject_quota_limits = {s.code: s.weekly_quota for s in subjects}
            
            # Build lab subjects list
            lab_subjects = [s.code for s in subjects if s.is_lab]
            
            # Build teacher preferences
            teacher_preferences = {}
            teacher_weekly_workload = {}
            teacher_duty_days = {}
            
            for teacher in teachers:
                teacher_id = teacher.employee_id
                teacher_weekly_workload[teacher_id] = teacher.max_weekly_hours
                teacher_duty_days[teacher_id] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                
                # Get preferences if exists
                try:
                    pref = TeacherPreference.objects.get(teacher=teacher)
                    teacher_preferences[teacher_id] = pref.preferred_time_slots or []
                except TeacherPreference.DoesNotExist:
                    teacher_preferences[teacher_id] = []
            
            # Initialize availability matrices
            teacher_list = list(teacher_weekly_workload.keys())
            num_days = len(serializer.validated_data.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']))
            num_slots = 7  # Default
            
            teacher_availability_matrix = initialize_teacher_availability(teacher_list, num_days, num_slots)
            
            lab_availability_matrix = {}
            for lab in labs:
                lab_availability_matrix[lab.name] = [[True] * num_slots for _ in range(num_days)]
            
            # Default time slots
            time_slots = serializer.validated_data.get('time_slots', {
                1: "9:00 - 9:55",
                2: "9:55 - 10:50",
                3: "11:10 - 12:05",
                4: "12:05 - 1:00",
                5: "1:20 - 2:15",
                6: "2:15 - 3:10",
                7: "3:30 - 4:25",
            })
            
            day_map = serializer.validated_data.get('day_map', {
                "Monday": 0,
                "Tuesday": 1,
                "Wednesday": 2,
                "Thursday": 3,
                "Friday": 4,
            })
            
            time_slot_map = serializer.validated_data.get('time_slot_map', {
                "9:00 - 9:55": 1,
                "9:55 - 10:50": 2,
                "11:10 - 12:05": 3,
                "12:05 - 1:00": 4,
                "1:20 - 2:15": 5,
                "2:15 - 3:10": 6,
                "3:30 - 4:25": 7,
            })
            
            working_days = serializer.validated_data.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
            
            # Run algorithm
            best_tt, final_teacher, final_lab, fitness_score = run_timetable_generation(
                teacher_subject_mapping=teacher_subject_mapping,
                total_sections=total_sections,
                total_classrooms=total_classrooms,
                total_labs=total_labs,
                teacher_preferences=teacher_preferences,
                teacher_weekly_workload=teacher_weekly_workload,
                special_subjects={},
                labs=lab_subjects,
                subject_quota_limits=subject_quota_limits,
                teacher_duty_days=teacher_duty_days,
                teacher_availability_matrix=teacher_availability_matrix,
                lab_availability_matrix=lab_availability_matrix,
                total_generations=serializer.validated_data['total_generations'],
                time_slots=time_slots,
                day_map=day_map,
                time_slot_map=time_slot_map,
                fixed_teacher_assignment=serializer.validated_data.get('fixed_teacher_assignment'),
                working_days=working_days,
            )
            
            # Save timetable
            timetable = Timetable.objects.create(
                college=college,
                name=serializer.validated_data['name'],
                academic_year=serializer.validated_data['academic_year'],
                semester=serializer.validated_data.get('semester', ''),
                status='generated',
                timetable_data=best_tt,
                fitness_score=fitness_score,
                generation_config=serializer.validated_data,
                created_by=request.user,
            )
            
            return Response({
                'timetable_id': str(timetable.id),
                'timetable': best_tt,
                'fitness_score': fitness_score,
                'teacher_availability': final_teacher,
                'lab_availability': final_lab,
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error generating timetable: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Failed to generate timetable: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
