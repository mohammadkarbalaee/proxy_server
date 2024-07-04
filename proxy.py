import socket
import threading
import hashlib
import os

# Constants
BUFFER_SIZE = 4096
CACHE_DIR = './cache'

# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

def hash_url(url):
    """Create a unique hash for the URL."""
    return hashlib.md5(url.encode()).hexdigest()

def cache_response(url, response):
    """Cache the response to a file with the URL's hash as the filename."""
    url_hash = hash_url(url)
    cache_file_path = os.path.join(CACHE_DIR, url_hash)
    with open(cache_file_path, 'wb') as cache_file:
        cache_file.write(response)

def get_cached_response(url):
    """Retrieve the cached response for a URL if it exists."""
    url_hash = hash_url(url)
    cache_file_path = os.path.join(CACHE_DIR, url_hash)
    if os.path.exists(cache_file_path):
        with open(cache_file_path, 'rb') as cache_file:
            return cache_file.read()
    return None

def handle_client(client_socket):
    """Handle the client's request."""
    request = client_socket.recv(BUFFER_SIZE)
    request_line = request.split(b'\n')[0]
    url = request_line.split(b' ')[1].decode()
    
    # Check if the response is in the cache
    cached_response = get_cached_response(url)
    if cached_response:
        client_socket.sendall(cached_response)
    else:
        # Parse the URL to extract the host and port
        http_pos = url.find("://")
        temp = url[(http_pos+3):] if http_pos != -1 else url
        port_pos = temp.find(":")
        webserver_pos = temp.find("/")
        webserver = ""
        port = -1

        if webserver_pos == -1:
            webserver_pos = len(temp)

        if port_pos == -1 or webserver_pos < port_pos:
            port = 80
            webserver = temp[:webserver_pos]
        else:
            port = int((temp[(port_pos+1):])[:webserver_pos-port_pos-1])
            webserver = temp[:port_pos]

        try:
            # Connect to the web server
            webserver_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            webserver_socket.connect((webserver, port))
            webserver_socket.sendall(request)
            
            # Receive response from web server
            response = b""
            while True:
                data = webserver_socket.recv(BUFFER_SIZE)
                if len(data) > 0:
                    response += data
                else:
                    break
            
            # Cache the response
            cache_response(url, response)

            # Send the response to the client
            client_socket.sendall(response)
            webserver_socket.close()
        except Exception as e:
            print(f"Error: {e}")
    
    client_socket.close()

def start_proxy_server(host='127.0.0.1', port=8888):
    """Start the proxy server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"[*] Listening on {host}:{port}")
    
    while True:
        client_socket, addr = server_socket.accept()
        print(f"[*] Accepted connection from {addr[0]}:{addr[1]}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()

if __name__ == "__main__":
    start_proxy_server()