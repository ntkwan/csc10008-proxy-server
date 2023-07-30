from socket import *
import sys
import os

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

    if is_cached(host_name):
        cached_data = get_cached_data(host_name)
        client_socket.send(cached_data)
    else:
        server_respone = get_server_respone(host_name, request)
        client_socket.send(server_respone)
        cache_data(host_name, server_respone)
        
    client_socket.close()

def get_server_info(request):
    request_data = request.decode()
    method = request_data.split(' ')[0]
    url = request_data.split(' ')[1]
    host_name = url.split('/')[2]
    return method, host_name

def is_whitelisted(host_name):
    with open(".config", "r") as file:
        line = file.readlines()[1]
    white_list = line.split('=')[1].split(', ')
    white_list[-1] = white_list[-1][:-1]
    return any(site in host_name for site in white_list)

def is_cached(host_name):
    # Kiểm tra xem trang web đã được lưu trữ trong bộ đệm hay chưa
    # và kiểm tra thời gian cache đã hết hạn chưa
    
    
    file_path = "cache/" + host_name
    return os.path.isfile(file_path)

def get_cached_data(host_name):
    file_path = "cache/" + host_name
    data = b""
    with open(file_path, "rb") as file:
        for line in file:
            data +=line
    return data

def get_server_respone(host_name, request):
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect((host_name, 80))
    server_socket.sendall(request)
    server_respone = b""
    
    # Phải đọc Content-Length trước
    # Giải quyết chunked
    
    
    data = server_socket.recv(4096)
    print(data.decode())
    server_respone += data
    
    
    server_socket.close()
    return server_respone

def cache_data(host_name, data):
    file_path = "cache/" + host_name
    with open(file_path, "wb") as file:
        file.write(data)


tcpSerSock = socket(AF_INET, SOCK_STREAM)
tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
tcpSerSock.bind((sys.argv[1], 8888))
tcpSerSock.listen(2)
print('Proxy Server is ready to receive connections...')


print('Ready to serve...')
tcpCliSock, addr = tcpSerSock.accept()
print('Received a connection from:', addr)
handle_client(tcpCliSock)

tcpSerSock.close()