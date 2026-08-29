from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError

def global_exception_handler(exc, context):
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    error_message = str(exc)
    
    if response is not None:
        # DRF exceptions (ValidationError, PermissionDenied, NotAuthenticated, etc.)
        if isinstance(response.data, dict) and 'detail' in response.data:
            error_message = response.data['detail']
        elif isinstance(response.data, list):
            error_message = response.data[0]
        elif isinstance(response.data, dict):
            # For validation errors mapped to fields
            first_key = list(response.data.keys())[0]
            first_error = response.data[first_key]
            if isinstance(first_error, list):
                error_message = f"{first_key}: {first_error[0]}"
            else:
                error_message = f"{first_key}: {first_error}"
                
        return Response({
            'success': False,
            'message': error_message,
            'data': None
        }, status=response.status_code)
    
    # Non-DRF exceptions
    if isinstance(exc, DjangoValidationError):
        return Response({
            'success': False,
            'message': str(exc.message if hasattr(exc, 'message') else exc),
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)
        
    elif isinstance(exc, IntegrityError):
        return Response({
            'success': False,
            'message': "Data integrity violation: Cannot delete or update resource because it is currently in use.",
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # Catch-all
    return Response({
        'success': False,
        'message': error_message if error_message else "Internal server error",
        'data': None
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
