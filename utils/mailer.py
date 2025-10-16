import smtplib
import csv
from email.message import EmailMessage
from datetime import datetime
import os

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

CSV_DIR = "csv_reports"
os.makedirs(CSV_DIR, exist_ok=True)

def export_csv(user_id, expenses):
    path = os.path.join(CSV_DIR, f"{user_id}_report.csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "amount", "category"])
        writer.writeheader()
        for e in expenses:
            writer.writerow({"date": e["date"], "amount": e["amount"], "category": e["category"]})
    return path

def send_email(recipient, file_path):
    msg = EmailMessage()
    msg['Subject'] = 'Your Monthly Expense Report'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient
    msg.set_content('Attached is your monthly expense report.')

    with open(file_path, 'rb') as f:
        msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=os.path.basename(file_path))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
