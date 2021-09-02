
import logging
from smtplib import SMTPException
import io
import datetime
import boto3
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from oscar.core.loading import get_model
from django.utils.text import slugify

from ecommerce.enterprise.utils import get_enterprise_customer

logger = logging.getLogger(__name__)

Product = get_model('catalogue', 'Product')


def send_new_codes_notification_email(site, email_address, enterprise_id, coupon_id):
    """
    Send new codes email notification to an enterprise customer.

    Arguments:
        site (str): enterprise customer site
        email_address (str): recipient email address of the enterprise customer
        enterprise_id (str): enterprise customer uuid
        coupon_id (str): id of the newly created coupon
    """
    enterprise_customer_object = get_enterprise_customer(site, enterprise_id)
    enterprise_slug = enterprise_customer_object.get('slug')

    try:
        send_mail(
            subject=settings.NEW_CODES_EMAIL_CONFIG['email_subject'],
            message=settings.NEW_CODES_EMAIL_CONFIG['email_body'].format(enterprise_slug=enterprise_slug),
            from_email=settings.NEW_CODES_EMAIL_CONFIG['from_email'],
            recipient_list=[email_address],
            fail_silently=False
        )
    except SMTPException:
        logger.exception(
            'New codes email failed for enterprise customer [%s] for coupon [%s]',
            enterprise_id,
            coupon_id
        )

    logger.info('New codes email sent to enterprise customer [%s] for coupon [%s]', enterprise_id, coupon_id)


def get_enterprise_from_product(product_id):
    """
    Retrieve enterprise_id from a given Product (coupon)

    :param product_id (str): Coupon product id
    :return: enterprise_id (str): enterprise customer uuid or None
    """
    try:
        product = Product.objects.get(pk=product_id)
        return product.attr.enterprise_customer_uuid
    except Product.DoesNotExist:
        return None


def upload_files_for_enterprise_coupons(files):
    uploaded_files = []
    if files and len(files) > 0:
        bucket_name = settings.AWS_EMAIL_TEMPLATE_BUCKET_NAME
        session = boto3.Session(
            aws_access_key_id=settings.AWS_EMAIL_TEMPLATE_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_EMAIL_TEMPLATE_SECRET_ACCESS_KEY
        )
        s3 = session.client('s3')

        for file in files:
            file_buf = io.BytesIO(bytes(file['contents'], encoding="raw_unicode_escape"))
            file_buf.seek(0)
            filename = datetime.datetime.now().strftime("%d-%m-%Y at %H.%M.%S") + " " + file['name']
            # key = quote(filename, safe="~()*!.'")
            key = slugify(filename)
            s3.upload_fileobj(file_buf, bucket_name, key)
            location = s3.get_bucket_location(Bucket=bucket_name)['LocationConstraint']
            url = f"https://{bucket_name}.s3.{location}.amazonaws.com/{key}"
            uploaded_files.append({'name': key, 'size': file['size'], 'url': url})
    return uploaded_files
