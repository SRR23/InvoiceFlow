
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from utils.permissions import IsBusinessUser
from .bulk_import import (
    MAX_FILE_BYTES,
    ImportParseError,
    client_import_template_csv_bytes,
    client_import_template_xlsx_bytes,
    run_client_import,
)
from .models import Client
from .serializers import (
    ClientImportResultSerializer,
    ClientSerializer,
)


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing clients.
    Only business users can access their own clients.
    """
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, IsBusinessUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['name', 'email', 'company']
    search_fields = ['name', 'email', 'company', 'phone']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return only clients belonging to the current user."""
        return Client.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Set the user when creating a new client."""
        serializer.save(user=self.request.user)

    @extend_schema(
        responses={200: ClientImportResultSerializer},
        description=(
            "Upload a UTF-8 CSV or .xlsx file with columns: name (required), "
            "email, phone, company, address. Duplicate emails in the file are skipped; "
            "rows matching an existing client email are skipped."
        ),
    )
    @action(detail=False, methods=['post'], url_path='import')
    def import_clients(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response(
                {'detail': 'No file uploaded. POST multipart/form-data with field name "file".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if getattr(upload, 'size', 0) and upload.size > MAX_FILE_BYTES:
            return Response(
                {
                    'detail': (
                        f'File is too large. Maximum size is {MAX_FILE_BYTES // (1024 * 1024)} MB.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = run_client_import(request.user, upload, upload.name or '')
        except ImportParseError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)

        message = None
        if result.had_no_data_rows:
            message = (
                'No data rows were found. Ensure there is a header row and at least one '
                'non-empty row below it. Unknown columns are ignored; use the template.'
            )
        body = {
            'created': result.created,
            'had_no_data_rows': result.had_no_data_rows,
            'message': message,
            'skipped_duplicate_in_file': result.skipped_duplicate_in_file,
            'skipped_existing_email': result.skipped_existing_email,
            'row_errors': result.row_errors,
        }
        serializer = ClientImportResultSerializer(data=body)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: {'description': 'CSV or XLSX attachment'}},
        description='Download a sample CSV or Excel file with the expected column headers.',
    )
    @action(detail=False, methods=['get'], url_path='import_template')
    def import_template(self, request):
        fmt = (request.query_params.get('format') or 'xlsx').strip().lower()
        if fmt == 'csv':
            data = client_import_template_csv_bytes()
            response = HttpResponse(
                data,
                content_type='text/csv; charset=utf-8',
            )
            response['Content-Disposition'] = (
                'attachment; filename="client_import_template.csv"'
            )
            return response
        if fmt in ('xlsx', 'excel'):
            data = client_import_template_xlsx_bytes()
            response = HttpResponse(
                data,
                content_type=(
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                ),
            )
            response['Content-Disposition'] = (
                'attachment; filename="client_import_template.xlsx"'
            )
            return response
        return Response(
            {'detail': 'Invalid format. Use ?format=csv or ?format=xlsx.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
