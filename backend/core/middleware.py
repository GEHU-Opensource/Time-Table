"""
Middleware for multi-tenant support.
"""
from django.http import Http404
from core.models import College


class TenantMiddleware:
    """Middleware to handle multi-tenancy based on subdomain or header."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get tenant from subdomain or X-College-Code header
        host = request.get_host().split(':')[0]
        subdomain = host.split('.')[0] if '.' in host else None
        
        college = None
        if subdomain and subdomain != 'www' and subdomain != 'admin':
            try:
                college = College.objects.get(subdomain=subdomain, is_active=True)
            except College.DoesNotExist:
                pass
        
        # Also check header for API requests
        if not college:
            college_code = request.headers.get('X-College-Code')
            if college_code:
                try:
                    college = College.objects.get(code=college_code, is_active=True)
                except College.DoesNotExist:
                    pass
        
        # Attach college to request
        request.college = college
        
        response = self.get_response(request)
        return response
