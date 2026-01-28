"""
URLs for core app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import views

router = DefaultRouter()
router.register(r'colleges', views.CollegeViewSet, basename='college')
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'teachers', views.TeacherViewSet, basename='teacher')
router.register(r'subjects', views.SubjectViewSet, basename='subject')
router.register(r'sections', views.SectionViewSet, basename='section')
router.register(r'classrooms', views.ClassroomViewSet, basename='classroom')
router.register(r'subject-teacher-mappings', views.SubjectTeacherMappingViewSet, basename='subject-teacher-mapping')
router.register(r'timetables', views.TimetableViewSet, basename='timetable')
router.register(r'teacher-preferences', views.TeacherPreferenceViewSet, basename='teacher-preference')
router.register(r'generate-timetable', views.GenerateTimetableViewSet, basename='generate-timetable')

urlpatterns = [
    path('', include(router.urls)),
]
