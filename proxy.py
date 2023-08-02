from socket import *
import time
import datetime
import threading
import sys
import os
import re
import gzip

if len(sys.argv) <= 1:
    print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server]')
    sys.exit(2)

def handle_client(client_socket):
    try:
        request = client_socket.recv(4096)
        method, url, host_name = get_server_info(request)
        if method == None:
            client_socket.close()
            return
        
        if not is_in_access_time() or not is_whitelisted(host_name) or method not in ['GET', 'POST', 'HEAD']:
            response = "HTTP/1.1 403 Forbidden\r\n\r\n<html><body><h1>403 Forbidden</h1></body></html>"
            client_socket.sendall(response.encode())
            client_socket.close()
            return
        
        print(host_name)
        print(url)
        if is_image_request(url):
            _, path = os.path.split(url)
            file_name = "cache/" + host_name.replace(".", "_") + "-" + path
            if os.path.exists(file_name):
                print("exist")
                response = "HTTP/1.1 200 OK\r\n\r\n"
                with open(file_name, "rb") as file:
                    image_data = file.read()
                client_socket.sendall(response.encode())
                client_socket.sendall(image_data)
                client_socket.close()
                return
            else:
                image_data, server_respone = get_image_data_respone(host_name, request)
                if server_respone != None:
                    cache_image(host_name, image_data, url)
                else:
                    server_respone = b"HTTP/1.1 403 Forbidden\r\n\r\n<html><body><h1>403 Forbidden</h1><h2>Cache time out. Refresh your host website</h2></body></html>"
                client_socket.sendall(server_respone)
                client_socket.close()
                return
                
        server_respone = get_server_respone(host_name, request)
        client_socket.sendall(server_respone)
        client_socket.close()
    except OSError:
        client_socket.close()
        pass

def get_server_info(request):
    try:
        request_data = request.decode()
        method = request_data.split(' ')[0]
        url = request_data.split(' ')[1]
        host_name = url.split('/')[2]
        return method, url, host_name
    except:
        return None, None, None
    
def is_in_access_time():
    now = datetime.datetime.now()
    access_start = now.replace(hour=TIME_LIMIT[0],minute=0,second=0,microsecond=0)
    access_end = now.replace(hour=TIME_LIMIT[1],minute=0,second=0,microsecond=0)
    return access_start <= now <= access_end

def is_whitelisted(host_name):
    with open("config", "r") as file:
        line = file.readlines()[1]
    white_list = line.split('=')[1].split(', ')
    white_list[-1] = white_list[-1][:-1]
    return any(site in host_name for site in white_list)

def is_image_request(url):
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico"]
    _, ext = os.path.splitext(url)
    return any(ext == ex for ex in image_extensions)

def get_server_respone(host_name, request):
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect((host_name, 80))
    server_socket.sendall(request)
    
    server_respone = server_socket.recv(1024)
    chunked_encoding = False
    header_end = server_respone.find(b"\r\n\r\n")
    headers = server_respone[:header_end]
    
    if header_end + 4 == len(server_respone):
        server_socket.close()
        return None
        
    chunked_encoding = "transfer-encoding: chunked" in headers.decode().lower()
    
    content_length = get_content_length(headers)
    if not chunked_encoding and content_length > 0:
        if len(server_respone) < header_end + 4 + content_length:
            length = content_length - (len(server_respone) - header_end - 4)
            while len(server_respone) < header_end + content_length + 4:
                server_respone += server_socket.recv(length)
    else:
        end_check = b'0'
        chunked_part = server_respone.split(b"\r\n\r\n")[1]
        chunks = chunked_part.split(b"\r\n")
        if end_check not in chunks:
            while True:
                data_chunk = server_socket.recv(1024)
                server_respone += data_chunk
                data_chunks = data_chunk.split(b"\r\n")
                if end_check in data_chunks:
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

def get_image_data_respone(host_name, request):
    server_respone = get_server_respone(host_name, request)
    if server_respone != None:
        image_data = server_respone.split(b"\r\n\r\n")[1]
    return image_data, server_respone

def cache_image(host_name, image_data, url):
    _, path = os.path.split(url)
    file_name = "cache/" + host_name.replace(".", "_") + "-" + path
    with open(file_name, "wb") as file:
        file.write(image_data)
    images_cache_time[file_name[6:]] = time.time()
    print(images_cache_time)
        
def cache_clean():
    while True:
        time.sleep(CACHE_TIME)
        current_time = time.time()
        for file in os.listdir("./cache"):
            if current_time - images_cache_time[file] > CACHE_TIME:
                os.remove(os.path.join("cache/", file))
                    

def get_config():
    with open("config", "r") as file:
        for line in file:
            if "cache_time" in line:
                CACHE_TIME = float(line.split('=')[1].strip())
            elif "whitelisting" in line:
                WHITE_LIST = line.split('=')[1].strip().split(', ')
            else:
                TIME_LIMIT = line.split('=')[1].strip().split('-')
                TIME_LIMIT[0] = int(TIME_LIMIT[0])
                TIME_LIMIT[1] = int(TIME_LIMIT[1])
    return CACHE_TIME, WHITE_LIST, TIME_LIMIT
   
def main():     
    tcpSerSock = socket(AF_INET, SOCK_STREAM)
    tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    tcpSerSock.bind((sys.argv[1], 8888))
    tcpSerSock.listen(2)
    print('Proxy Server is ready to receive connections...')

    if not os.path.exists("./cache"):
        os.makedirs("./cache")

    cache_clean_thread = threading.Thread(target=cache_clean, daemon=True)
    cache_clean_thread.start()
    
    
    while True:
        try:
            print('Ready to serve...')
            tcpCliSock, addr = tcpSerSock.accept()
            print('Received a connection from:', addr)
            handle_client(tcpCliSock)
            client_thread = threading.Thread(target=handle_client, args=(tcpCliSock,))
            client_thread.start()   
            print("="*50)
        except KeyboardInterrupt:
            print("Exiting program...")
            break
    tcpSerSock.close()
    

CACHE_TIME, WHITE_LIST, TIME_LIMIT = get_config()
images_cache_time = {}
main()
