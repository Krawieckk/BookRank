from celery import shared_task
from django.core.mail import EmailMultiAlternatives


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_email_task(self, subject, body, from_email, to, html_body=None, headers=None, reply_to=None):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=from_email,
        to=to,
        headers=headers or None,
        reply_to=reply_to or None,
    )
    if html_body:
        msg.attach_alternative(html_body, "text/html")
    msg.send()