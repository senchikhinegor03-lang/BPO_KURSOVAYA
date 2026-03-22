"""
Custom middleware for security enhancements.
"""


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers and remove version information leakage.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if 'Server' in response:
                del response['Server']
        except (KeyError, AttributeError):
            pass

        try:
            response['Server'] = ''
        except Exception:
            pass

        response['X-Content-Type-Options'] = 'nosniff'
        if 'X-Frame-Options' not in response:
            response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        return response
