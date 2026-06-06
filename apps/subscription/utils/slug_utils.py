import logging
import uuid
from datetime import datetime

from django.utils.text import slugify

logger = logging.getLogger(__name__)


def generate_unique_slug(slug_content, instance, suffix_length=10):
    slug = slugify(slug_content)
    kclass = instance.__class__
    while kclass.objects.filter(slug=slug).exists():
        logger.debug('slug collision: %s %s', slug, kclass.__name__)
        slug = f'{slug}-{uuid.uuid4().hex[:suffix_length]}'
    return slug





def generate_unique_invoice_code(model, prefix="INV"):
    """
    Generate unique invoice-like codes for models that store either
    ``invoice_number`` (subscription invoices) or ``number`` (legacy/common invoice style).
    """
    unique_field_name = "invoice_number"
    model_field_names = {field.name for field in model._meta.fields}
    if "invoice_number" not in model_field_names and "number" in model_field_names:
        unique_field_name = "number"

    while True:  # Keep generating until a unique code is found
        # current_datetime = datetime.now().strftime("%M%S%f")[:10] 
        current_datetime = datetime.now().strftime("%y%m%d%S")  # Format: YYMMDDSS 
        unique_id = str(uuid.uuid4().int)[:5]  
        code = f"{prefix}{current_datetime}{unique_id}"

        # Check if the generated code already exists
        if not model.objects.filter(**{unique_field_name: code}).exists():
            return code  # Return only if unique