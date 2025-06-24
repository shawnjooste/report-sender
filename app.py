from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def send_email(to_email, subject, body, attachment_path=None):
    """Send email with optional PDF attachment"""
    try:
        gmail_user = os.getenv('GMAIL_USER')
        gmail_password = os.getenv('GMAIL_APP_PASSWORD')
        
        if not gmail_user or not gmail_password:
            return False, "Gmail credentials not set in .env file"
        
        # Create message
        msg = MimeMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MimeText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MimeBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(attachment_path)}',
            )
            msg.attach(part)
        
        # Send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        text = msg.as_string()
        server.sendmail(gmail_user, to_email, text)
        server.quit()
        
        # Log sent email
        with open('sent_emails.txt', 'a') as f:
            f.write(f"To: {to_email}, Subject: {subject}, Attachment: {attachment_path or 'None'}\n")
        
        return True, "Email sent successfully"
    
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def log_email_action(to_email, subject, attachment_path=None):
    """Log email action to file instead of sending"""
    with open('sent_emails.txt', 'a') as f:
        f.write(f"[LOG ONLY] To: {to_email}, Subject: {subject}, Attachment: {attachment_path or 'None'}\n")

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main form page and form submission handler"""
    if request.method == 'GET':
        return render_template('form.html')
    
    # Handle form submission
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    client_name = f"{first_name} {last_name}"
    client_email = request.form.get('email')
    is_exposed = request.form.get('exposed') == 'yes'
    
    if not client_name or not client_email:
        flash('Please fill in all required fields', 'error')
        return redirect(url_for('index'))
    
    attachment_path = None
    
    if is_exposed:
        # Handle file upload for exposed clients
        file = request.files.get('attachment')
        if file and file.filename and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            attachment_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(attachment_path)
        else:
            flash('Please upload a PDF report for exposed clients', 'error')
            return redirect(url_for('index'))
        
        # Send warning email with attachment
        subject = f"Security Alert - Action Required for {client_name}"
        body = f"""Dear {client_name},

We have detected that your credentials may have been exposed on the dark web. Please review the attached report and take immediate action to secure your accounts.

Recommended actions:
1. Change all passwords mentioned in the report
2. Enable two-factor authentication where possible
3. Monitor your accounts for suspicious activity

If you have any questions, please contact us immediately.

Best regards,
Security Team"""
        
        # Try to send email, fall back to logging if credentials not set
        success, message = send_email(client_email, subject, body, attachment_path)
        if success:
            flash(f'Security alert email sent to {client_email}', 'warning')
        else:
            log_email_action(client_email, subject, attachment_path)
            flash(f'Email credentials not configured. Action logged for {client_email}: {message}', 'info')
    
    else:
        # Send reassuring email
        subject = f"Security Report - All Clear for {client_name}"
        body = f"""Dear {client_name},

Good news! Our latest scan of the dark web has not found any of your credentials exposed.

Your current security status looks good, but we recommend:
1. Continue using strong, unique passwords
2. Keep two-factor authentication enabled
3. Stay vigilant for suspicious activities

We will continue monitoring and will notify you if anything changes.

Best regards,
Security Team"""
        
        # Try to send email, fall back to logging if credentials not set
        success, message = send_email(client_email, subject, body)
        if success:
            flash(f'All clear email sent to {client_email}', 'success')
        else:
            log_email_action(client_email, subject)
            flash(f'Email credentials not configured. Action logged for {client_email}: {message}', 'info')
    
    return redirect(url_for('index'))

@app.route('/import')
def import_page():
    """Import page for bulk operations"""
    return render_template('import.html')

@app.route('/logs')
def view_logs():
    """View sent email logs"""
    try:
        with open('sent_emails.txt', 'r') as f:
            logs = f.readlines()
        return f"<h2>Email Logs</h2><pre>{''.join(logs)}</pre><br><a href='/'>Back to Form</a>"
    except FileNotFoundError:
        return "<h2>No logs found</h2><br><a href='/'>Back to Form</a>"

@app.route('/config')
def config_status():
    """Show configuration status"""
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')
    
    config_html = f"""
    <h2>Configuration Status</h2>
    <p><strong>Gmail User:</strong> {'✅ Set' if gmail_user and gmail_user != 'your_gmail_address@gmail.com' else '❌ Not configured'}</p>
    <p><strong>Gmail App Password:</strong> {'✅ Set' if gmail_password and gmail_password != 'your_gmail_app_password' else '❌ Not configured'}</p>
    
    <h3>To Configure Email:</h3>
    <ol>
        <li>Edit the <code>.env</code> file in your project directory</li>
        <li>Replace <code>your_gmail_address@gmail.com</code> with your actual Gmail address</li>
        <li>Replace <code>your_gmail_app_password</code> with your Gmail app password</li>
        <li>Restart the server</li>
    </ol>
    
    <p><a href="https://support.google.com/accounts/answer/185833?hl=en">How to create a Gmail app password</a></p>
    <br><a href="/">Back to Form</a>
    """
    return config_html

if __name__ == '__main__':
    print("Starting Dark Web Report Sender...")
    print("Server will be available at: http://127.0.0.1:5000")
    print("Configuration status: http://127.0.0.1:5000/config")
    app.run(debug=True, host='127.0.0.1', port=5000) 