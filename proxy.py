from socket import *
import sys

if len(sys.argv) <= 1:
    print('Usage : "python ProxyServer.py server_ip"\n[server_ip : It is the IP Address Of Proxy Server]')
    sys.exit(2)

# Create and set up socket server
tcpSerSock = socket(AF_INET, SOCK_STREAM)
tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
tcpSerSock.bind((sys.argv[1], 8888))
tcpSerSock.listen(2)

print('Proxy Server is ready to receive connections...')

    # Start receiving data from the client
print('Ready to serve...')
tcpCliSock, addr = tcpSerSock.accept()
print('Received a connection from:', addr)
request = tcpCliSock.recv(4096)  # Receive data from client
request_data = request.decode()
print(request_data)

    # Extract the filename from the given request
# filename = request.split()[1].decode().partition("//")[2][:-1]
# print(f"filename: {filename}")

lines = request_data.split("\r\n")[1]
hostn = lines.split(' ')[1]
print(hostn)

c = socket(AF_INET, SOCK_STREAM)
c.connect((hostn, 80))
c.sendall(request)
respone = b""
respone += c.recv(4096)
# while True:
#     data = c.recv(4096)
#     if not data:
#         break
#     respone += data
tcpCliSock.sendall(respone)

c.close()

tcpCliSock.close()
    
tcpSerSock.close()