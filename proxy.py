from socket import *
import time
import sys
import os
import re

if len(sys.argv) <= 1:
    print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server]')
    sys.exit(2)

def handle_client(client_socket):
    request = client_socket.recv(4096)
    method, host_name = get_server_info(request)
    
    if not is_whitelisted(host_name) or method not in ['GET', 'POST', 'HEAD']:
        response = "HTTP/1.1 403 Forbidden\r\n\r\n<html><body><h1>403 Forbidden</h1></body></html>"
        client_socket.send(response.encode())
        client_socket.close()
        return
    
    server_respone = get_server_respone(host_name, request)
    client_socket.send(server_respone)

    try:
        image_urls = extract_image_url(server_respone.decode())
        cache_image(image_urls, host_name)
    except UnicodeDecodeError:
        pass
    client_socket.close()

def get_server_info(request):
    request_data = request.decode()
    method = request_data.split(' ')[0]
    url = request_data.split(' ')[1]
    host_name = url.split('/')[2]
    return method, host_name

def is_whitelisted(host_name):
    with open("config", "r") as file:
        line = file.readlines()[1]
    white_list = line.split('=')[1].split(', ')
    white_list[-1] = white_list[-1][:-1]
    return any(site in host_name for site in white_list)

def get_server_respone(host_name, request):
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect((host_name, 80))
    server_socket.sendall(request)
    
    server_respone = server_socket.recv(1024)
    chunked_encoding = False
    header_end = server_respone.find(b"\r\n\r\n")
    headers = server_respone[:header_end]
    chunked_encoding = "transfer-encoding: chunked" in headers.decode().lower()
    
    content_length = get_content_length(headers)
    if not chunked_encoding and content_length > 0:
        if len(server_respone) < header_end + 4 + content_length:
            length = content_length - (len(server_respone) - header_end - 4)
            while len(server_respone) < header_end + content_length + 4:
                server_respone += server_socket.recv(length)
    else:
        while True:
            data_chunk = server_socket.recv(1024)
            time.sleep(2.0)
            if len(data_chunk) == 1024:
                server_respone += data_chunk
            else:
                server_respone += data_chunk
                break
    
    server_socket.close()
    return server_respone

def get_content_length(headers):
    lines = headers.split(b"\r\n")
    for line in lines:
        if line.startswith(b"Content-Length:") or line.startswith(b"content-length"):
            length = line.split(b":")[1].strip()
            return int(length)
    return 0

def extract_image_url(data):
    pattern = r'<img\s+[^>]*src="([^"]+)"[^>]*>'
    image_urls = re.findall(pattern, data)
    return image_urls

def get_image_data(image_path, host_name):
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect((host_name, 80))
    request = f"GET {image_path} HTTP/1.1\r\nHost: {host_name}\r\nConnection: close\r\n\r\n"
    server_socket.sendall(request.encode())
    
    respone = b""
    respone = server_socket.recv(1024)
    header_end = respone.find(b"\r\n\r\n")
    headers = respone[:header_end]
    content_length = get_content_length(headers)
    
    if len(respone) < header_end + 4 + content_length:
        length = content_length - (len(respone) - header_end - 4)
        while len(respone) < header_end + content_length + 4:
            respone += server_socket.recv(length)
    respone = respone[header_end + 4:]
    
    server_socket.close()
    return respone

def cache_image(image_urls, host_name):
    for url in image_urls:
        image_data = get_image_data(url, host_name)
        _, ext = os.path.split(url)
        file_name = "cache/" + host_name.replace(".", "_") + "-" + ext
        with open(file_name, "wb") as file:
            file.write(image_data)
        
tcpSerSock = socket(AF_INET, SOCK_STREAM)
tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
tcpSerSock.bind((sys.argv[1], 8888))
tcpSerSock.listen(2)
print('Proxy Server is ready to receive connections...')

if not os.path.exists("./cache"):
    os.makedirs("./cache")

print('Ready to serve...')
tcpCliSock, addr = tcpSerSock.accept()
print('Received a connection from:', addr)
handle_client(tcpCliSock)

tcpSerSock.close()