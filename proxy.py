from socket import *
import time
import datetime
import threading
import sys
import os

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
        
        print(url)
        if is_image_request(url):
            _, path = os.path.split(url)
            file_name = "cache/" + host_name.replace(".", "_") + "-" + path
            if os.path.exists(file_name):
                response = "HTTP/1.1 200 OK\r\n\r\n"
                with open(file_name, "rb") as file:
                    image_data = file.read()
                client_socket.sendall(response.encode())
                client_socket.sendall(image_data)
                client_socket.close()
                return
            else:
                image_data, server_response = get_image_data_respone(host_name, request)
                if image_data != b'':
                    cache_image(host_name, image_data, url)
                client_socket.sendall(server_response)
                client_socket.close()
                return
        
        server_response = get_server_respone(host_name, request)
        client_socket.sendall(server_response)
        client_socket.close()
    except OSError:
        client_socket.close()

def get_server_info(request):
    try:
        request_data = request.decode()
        method = request_data.split(' ')[0]
        url = request_data.split(' ')[1]
        host_name = url.split('/')[2]
        return method, url, host_name
    except:
        return None, None, None

def get_status(server_respone):
    buffer = server_respone.split(b'\r\n')[0]
    status = buffer.split(b' ')[1]
    return status

def get_connection_close(server_respone):
    connection = "connection: close" in server_respone.decode().lower()
    return connection

def get_image_data_respone(host_name, request):
    server_respone = get_server_respone(host_name, request)
    if get_status(server_respone) in error_codes:
        return b'', server_respone
    
    image_data = server_respone.split(b"\r\n\r\n")[1]
    return image_data, server_respone

def get_server_respone(host_name, request):
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect((host_name, 80))
    server_socket.sendall(request)
    
    server_respone = server_socket.recv(1024)
    chunked_encoding = False
    header_end = server_respone.find(b"\r\n\r\n")
    headers = server_respone[:header_end]
    
    if get_status(server_respone) in error_codes:
        server_respone = "HTTP/1.1 403 Forbidden\r\n\r\n<html><body><h1>403 Forbidden</h1></body></html>"
        return server_respone.encode()
    
    if (get_connection_close(headers)):
        while True:
            data_chunk = server_socket.recv(1024)
            if (data_chunk):
                server_respone += data_chunk
            else:
                return server_respone

    if header_end + 4 != len(server_respone):    
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

def cache_image(host_name, image_data, url):
    path = url.split(host_name)[1]
    file_name = "cache/" + host_name.replace(".", "_") + path.replace("/","-")
    with open(file_name, "wb") as file:
        file.write(image_data)
    images_cache_time[file_name[6:]] = time.time()
        
def cache_clean():
    while True:
        time.sleep(CACHE_TIME)
        current_time = time.time()
        for file in os.listdir("./cache"):
            if current_time - images_cache_time[file] > CACHE_TIME:
                print("deleted", file)
                os.remove(os.path.join("cache/", file))
                recache_image(file)

def recache_image(file):
    host_name = file.split('-')[0].replace("_",".")
    paths = file.split('-')[1:]
    url = "http://" + host_name
    for path in paths:
        url += "/" + path
 
    request = f"GET {url} HTTP/1.1\r\nHost: {host_name}\r\n\r\n"
    image_data, _ = get_image_data_respone(host_name,request.encode())
    cache_image(host_name, image_data, url)
    
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
    if len(sys.argv) <= 1:
        print('Usage : "python proxy.py [server_ip]"\n[server_ip : IP address of proxy server]')
        sys.exit(2)
    
    tcpSerSock = socket(AF_INET, SOCK_STREAM)
    tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    tcpSerSock.bind((sys.argv[1], 8888))
    tcpSerSock.listen(WEB_CLIENT)
    print('Proxy server is ready to receive connections...')

    if not os.path.exists("./cache"):
        os.makedirs("./cache")
    else:
        for file in os.listdir("./cache"):
            os.remove(os.path.join("./cache",file))
            
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
WEB_CLIENT = 5
error_codes = [b'405', b'404', b'403', b'401', b'400', b'408', b'500', b'502', b'503', b'100']
images_cache_time = {}
main()
