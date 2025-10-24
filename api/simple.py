from http.server import BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <html>
            <head><title>Parking System</title></head>
            <body>
                <h1>Parking Billing System</h1>
                <p>System is being deployed. Please check back later.</p>
            </body>
        </html>
        """
        self.wfile.write(html.encode())
        return
