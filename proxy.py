import socket
import threading
import os
import hashlib
import time
import csv

PORT = 8888
CACHE_DIR = './cache'
BUFFER_SIZE = 4096
LOG_FILE = 'request_logs.csv'
fieldnames = ['Request ID', 'URL', 'Start Time', 'End Time', 'Elapsed Time']

def initialize_log_file():
    with open(LOG_FILE, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def get_cache_key(url):
    return hashlib.md5(url.encode()).hexdigest()

def log_data(request_id, url, start_time, end_time):
    elapsed_time = end_time - start_time
    with open(LOG_FILE, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow({
            'Request ID': request_id,
            'URL': url,
            'Start Time': start_time,
            'End Time': end_time,
            'Elapsed Time': elapsed_time
        })

def handle_client(client_socket):
    global request_counter

    with counter_lock:
        request_id = request_counter
        request_counter += 1

    start_time = time.time()

    try:
        request = client_socket.recv(BUFFER_SIZE).decode()
        headers = request.split('\r\n')
        if len(headers) < 1:
            client_socket.close()
            return

        first_line = headers[0].split()
        if len(first_line) < 2:
            client_socket.close()
            return

        method = first_line[0]
        url = first_line[1][1:]

        if not url.startswith("www."):
            client_socket.close()
            return

        cache_key = get_cache_key(url)
        cache_file_path = os.path.join(CACHE_DIR, cache_key)

        if os.path.exists(cache_file_path):
            with open(cache_file_path, 'rb') as cache_file:
                response = cache_file.read()
                client_socket.sendall(response)
            log_data(request_id, url, start_time, time.time())
            client_socket.close()
            return

        fetch_from_server(client_socket, method, url, headers, cache_file_path, request_id, start_time)

    except Exception as e:
        handle_error(client_socket, str(e))

    client_socket.close()
    log_data(request_id, url, start_time, time.time())

def fetch_from_server(client_socket, method, url, headers, cache_file_path, request_id, start_time):
    try:
        web_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        web_server_socket.connect((url.split('/')[0], 80))

        if method == 'GET':
            web_server_socket.sendall(f"GET /{'/'.join(url.split('/')[1:])} HTTP/1.0\r\nHost: {url.split('/')[0]}\r\n\r\n".encode())
        elif method == 'POST':
            content_length = 0
            for header in headers:
                if header.lower().startswith('content-length:'):
                    content_length = int(header.split()[1])
                    break
            post_data = client_socket.recv(content_length).decode()
            web_server_socket.sendall(f"POST /{'/'.join(url.split('/')[1:])} HTTP/1.0\r\nHost: {url.split('/')[0]}\r\nContent-Length: {content_length}\r\n\r\n{post_data}".encode())

        response = b""
        while True:
            data = web_server_socket.recv(BUFFER_SIZE)
            if not data:
                break
            response += data

        web_server_socket.close()

        response_str = response.decode('utf-8', errors='ignore')
        status_code = int(response_str.split('\n')[0].split()[1])

        if not str(status_code).startswith("2"):
            handle_error(client_socket, f"{status_code}: {response_str}", status_code=status_code)
            return

        with open(cache_file_path, 'wb') as cache_file:
            cache_file.write(response)

        client_socket.sendall(response)

    except Exception as e:
        handle_error(client_socket, str(e))

def handle_error(client_socket, error_message, status_code=500):
    error_response = f"HTTP/1.1 {status_code} {error_message}\r\nContent-Length: {len(error_message)}\r\n\r\n{error_message}"
    client_socket.sendall(error_response.encode())


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', PORT))
    server_socket.listen(5)
    print(f"Proxy server is running on port {PORT}")

    while True:
        client_socket, addr = server_socket.accept()
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()

if __name__ == "__main__":
    initialize_log_file()
    ensure_cache_dir()
    request_counter = 0
    counter_lock = threading.Lock()
    start_server()
