# Dark Web Report Sender

A simple Flask app to send report emails to clients based on their exposure status.

## Features
- Send a reassuring email if credentials are not exposed
- Send a warning email with PDF attachment if credentials are exposed
- Uses Gmail SMTP (requires Gmail app password)

## Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables for Gmail:
   ```bash
   export GMAIL_USER='your_gmail_address@gmail.com'
   export GMAIL_APP_PASSWORD='your_gmail_app_password'
   ```
   - [How to create a Gmail app password](https://support.google.com/accounts/answer/185833?hl=en)

4. Run the app:
   ```bash
   python app.py
   ```

5. Open your browser to [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Usage
- Fill out the form.
- If the client is exposed, upload a PDF report.
- Submit to send the appropriate email. 