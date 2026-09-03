import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from flask import current_app

def send_email(subject: str, recipients: list[str], html_body: str, text_body: str = None, attachment: tuple[str, bytes, str] = None) -> bool:
    """
    Sends an email using configured SMTP settings.
    attachment format: (filename, bytes_data, mime_type)
    """
    server = current_app.config.get('MAIL_SERVER')
    port = current_app.config.get('MAIL_PORT', 587)
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')
    sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@vsmt.edu.in')

    if not server or not recipients:
        current_app.logger.warning("Email not sent: MAIL_SERVER or recipients not specified.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    if html_body:
        msg.attach(MIMEText(html_body, 'html'))

    if attachment:
        filename, file_bytes, mime_type = attachment
        part = MIMEApplication(file_bytes)
        part.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(part)

    try:
        smtp = smtplib.SMTP(server, port, timeout=10)
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.sendmail(sender, recipients, msg.as_string())
        smtp.quit()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return False
