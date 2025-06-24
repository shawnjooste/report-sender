from flask import Flask, render_template_string, request, jsonify
from werkzeug.utils import secure_filename
import os
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from email.mime.base import MimeBase
from email import encoders
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vercel-secret-key-change-this')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# HTML template inline (since Vercel serverless doesn't handle separate template files well)
FORM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dark Web Report Sender</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script>
        function toggleAttachment() {
            const exposedYes = document.getElementById('exposed_yes').checked;
            document.getElementById('attachment_group').style.display = exposedYes ? 'block' : 'none';
        }
        
        async function submitForm(event) {
            event.preventDefault();
            const formData = new FormData(event.target);
            const submitBtn = document.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Sending...';
            
            try {
                const response = await fetch('/', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    document.getElementById('result').innerHTML = 
                        `<div class="alert alert-success">${result.message}</div>`;
                    event.target.reset();
                    toggleAttachment();
                } else {
                    document.getElementById('result').innerHTML = 
                        `<div class="alert alert-danger">${result.error}</div>`;
                }
            } catch (error) {
                document.getElementById('result').innerHTML = 
                    `<div class="alert alert-danger">Error: ${error.message}</div>`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        }
    </script>
</head>
<body class="bg-light">
<div class="container mt-5">
    <h2>Dark Web Report Sender</h2>
    <div id="result"></div>
    
    <form onsubmit="submitForm(event)" class="card p-4 shadow-sm">
        <div class="mb-3">
            <label for="first_name" class="form-label">First Name</label>
            <input type="text" class="form-control" id="first_name" name="first_name" required>
        </div>
        <div class="mb-3">
            <label for="last_name" class="form-label">Last Name</label>
            <input type="text" class="form-control" id="last_name" name="last_name" required>
        </div>
        <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input type="email" class="form-control" id="email" name="email" required>
        </div>
        <div class="mb-3">
            <label class="form-label">Credentials Exposed?</label><br>
            <div class="form-check form-check-inline">
                <input class="form-check-input" type="radio" name="exposed" id="exposed_no" value="no" checked onclick="toggleAttachment()">
                <label class="form-check-label" for="exposed_no">No</label>
            </div>
            <div class="form-check form-check-inline">
                <input class="form-check-input" type="radio" name="exposed" id="exposed_yes" value="yes" onclick="toggleAttachment()">
                <label class="form-check-label" for="exposed_yes">Yes</label>
            </div>
        </div>
        <div class="mb-3" id="attachment_group" style="display:none;">
            <label for="attachment" class="form-label">PDF Report Attachment</label>
            <input class="form-control" type="file" id="attachment" name="attachment" accept="application/pdf">
        </div>
        <button type="submit" class="btn btn-primary">Send Email</button>
    </form>
    
    <div class="mt-4">
        <a href="/config" class="btn btn-outline-secondary">Check Configuration</a>
    </div>
</div>
<script>
    window.onload = toggleAttachment;
</script>
</body>
</html>
"""

def send_email(to_email, subject, body, attachment_data=None, attachment_filename=None):
    """Send email with optional PDF attachment"""
    try:
        gmail_user = os.environ.get('GMAIL_USER')
        gmail_password = os.environ.get('GMAIL_APP_PASSWORD')
        
        if not gmail_user or not gmail_password:
            return False, "Gmail credentials not set in environment variables"
        
        # Create message
        msg = MimeMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MimeText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_data and attachment_filename:
            part = MimeBase('application', 'octet-stream')
            part.set_payload(attachment_data)
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment_filename}',
            )
            msg.attach(part)
        
        # Send email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        text = msg.as_string()
        server.sendmail(gmail_user, to_email, text)
        server.quit()
        
        # Log to Vercel function logs
        print(f"EMAIL SENT: To: {to_email}, Subject: {subject}, Attachment: {attachment_filename or 'None'}")
        
        return True, "Email sent successfully"
    
    except Exception as e:
        print(f"EMAIL ERROR: {str(e)}")
        return False, f"Error sending email: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main form page and form submission handler"""
    if request.method == 'GET':
        return render_template_string(FORM_HTML)
    
    # Handle form submission
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    client_name = f"{first_name} {last_name}"
    client_email = request.form.get('email')
    is_exposed = request.form.get('exposed') == 'yes'
    
    if not first_name or not last_name or not client_email:
        return jsonify({"error": "Please fill in all required fields"}), 400
    
    attachment_data = None
    attachment_filename = None
    
    if is_exposed:
        # Handle file upload for exposed clients
        file = request.files.get('attachment')
        if file and file.filename and file.filename.endswith('.pdf'):
            attachment_filename = secure_filename(file.filename)
            attachment_data = file.read()
        else:
            return jsonify({"error": "Please upload a PDF report for exposed clients"}), 400
        
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
        
        success, message = send_email(client_email, subject, body, attachment_data, attachment_filename)
        if success:
            return jsonify({"message": f"Security alert email sent to {client_email}"}), 200
        else:
            return jsonify({"error": f"Failed to send email: {message}"}), 500
    
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
        
        success, message = send_email(client_email, subject, body)
        if success:
            return jsonify({"message": f"All clear email sent to {client_email}"}), 200
        else:
            return jsonify({"error": f"Failed to send email: {message}"}), 500

@app.route('/config')
def config_status():
    """Show configuration status"""
    gmail_user = os.environ.get('GMAIL_USER')
    gmail_password = os.environ.get('GMAIL_APP_PASSWORD')
    
    config_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Configuration Status</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
    <div class="container mt-5">
        <h2>Configuration Status</h2>
        <div class="card p-4">
            <p><strong>Gmail User:</strong> {'✅ Set' if gmail_user and gmail_user != 'your_gmail_address@gmail.com' else '❌ Not configured'}</p>
            <p><strong>Gmail App Password:</strong> {'✅ Set' if gmail_password and gmail_password != 'your_gmail_app_password' else '❌ Not configured'}</p>
            
            <h3>To Configure Email:</h3>
            <ol>
                <li>Go to your Vercel project dashboard</li>
                <li>Navigate to Settings → Environment Variables</li>
                <li>Add <code>GMAIL_USER</code> with your Gmail address</li>
                <li>Add <code>GMAIL_APP_PASSWORD</code> with your Gmail app password</li>
                <li>Redeploy your project</li>
            </ol>
            
            <p><a href="https://support.google.com/accounts/answer/185833?hl=en" target="_blank">How to create a Gmail app password</a></p>
        </div>
        <br><a href="/" class="btn btn-primary">Back to Form</a>
    </div>
    </body>
    </html>
    """
    return config_html

@app.route('/')
def hello():
    return 'Hello World from Vercel!'

@app.route('/test')
def test():
    return {"status": "success", "message": "API endpoint working"}

@app.route("/")
def home():
    return "Dark Web Report Sender - Basic Test Working!"

@app.route("/about")
def about():
    return "About page working"

# This is the entry point for Vercel
# Vercel will automatically call the 'app' variable 

if __name__ == '__main__':
    app.run() 