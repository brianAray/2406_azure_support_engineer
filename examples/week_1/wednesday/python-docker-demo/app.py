from http.server import SimpleHTTPRequestHandler, HTTPServer

class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>This has been changed</h1>")

server = HTTPServer(("0.0.0.0", 8081), MyHandler)
print("Server running on port 8081")
server.serve_forever()