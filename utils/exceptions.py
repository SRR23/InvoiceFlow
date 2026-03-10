"""
Custom exception handlers for DRF.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    Provides consistent error response format.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If response is None, it's an unhandled exception
    if response is None:
        logger.exception(f"Unhandled exception: {exc}")
        return Response(
            {
                'error': 'An unexpected error occurred',
                'detail': str(exc) if hasattr(exc, '__str__') else 'Unknown error'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Customize the response data structure
    custom_response_data = {
        'error': 'An error occurred',
        'detail': response.data
    }
    
    # Handle validation errors
    if isinstance(response.data, dict):
        if 'detail' in response.data:
            custom_response_data['detail'] = response.data['detail']
        elif 'non_field_errors' in response.data:
            custom_response_data['detail'] = response.data['non_field_errors']
        else:
            custom_response_data['detail'] = response.data
    
    response.data = custom_response_data
    
    return response
