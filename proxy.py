from socket import *
import time
import datetime
import threading
import sys
import os

def is_in_access_time():
    now = datetime.datetime.now() # Get the current time
    access_start = now.replace(hour=TIME_LIMIT[0],minute=0,second=0,microsecond=0)
    access_end = now.replace(hour=TIME_LIMIT[1],minute=0,second=0,microsecond=0)
    return access_start <= now <= access_end

def is_whitelisted(host_name):
    line = open("config", "r").readlines()[1]
    white_list = line.split('=')[1].strip().split(', ')
    return any(site in host_name for site in white_list)

def is_image_request(url):
    return any(ex in url for ex in image_extensions)

def get_server_info(request):
    try:
        request_data = request.decode() # Convert the request from bytes to string
        method = request_data.split(' ')[0]
        url = request_data.split(' ')[1]
        host_name = url.split('/')[2]
        return method, url, host_name
    except:
        return None, None, None

def error_response():
    return b"HTTP/1.1 403 Forbidden\r\n\r\n" + open('./forbidden_page.html', 'rb').read()

def handle_client(client_socket):
    try:
        request = client_socket.recv(4096) # Get the header of the request
        method, url, host_name = get_server_info(request) # Get the request information

        # If the request is from invalid connection, close the connection
        print('Try to connect to', url)
        if method == None:
            return (print('Failed to connect!'), client_socket.close())

        # If the request is not in access time or not in whitelist or not [GET, POS, HEAD] request, return 403 Forbidden
        if not is_in_access_time() or not is_whitelisted(host_name) or method not in ['GET', 'POST', 'HEAD']:
            client_socket.sendall(error_response())
            return (print('Error: 403 Forbidden'), client_socket.close())
        
        # If the request is image request, check the cache
        if is_image_request(url):
            path = url.split(host_name)[1]
            img_ext = ""
            for ex in image_extensions:
                if ex in url:
                    img_ext = ex
            file_name = "cache/" + host_name.replace(".", "dot=") + path.split(img_ext)[0].replace("?","qm=").replace("/","sla=").replace(".", "dot=").replace("#","sharp=") + img_ext
            response = b"HTTP/1.1 200 OK\r\nCache-Control: no-store\r\n\r\n" 
            client_socket.sendall(response)
            
            # If the image is in cache, return the image
            if os.path.isfile(file_name):
                image_data = open(file_name, 'rb').read()
                client_socket.sendall(image_data)
                print('Image:', file_name, 'found in cache!')
            else: # If the image is not in cache, request the image from server and cache it
                image_data = get_image_data_response(host_name, request)
                if image_data != b'':
                    cache_image(host_name, image_data, url)
                    client_socket.sendall(image_data)
                    
            return (client_socket.close())

        # If the request is website homepage, add '/' to the method        
        if (url[len(url) - 1] == url[5]):
            lines = request.decode().split(url)
            request = lines[0] + url[5] + lines[1]
            request = request.encode()

        # If the request is not image request, get the response from server and return it to client
        server_response = get_server_response(host_name, request)
        client_socket.sendall(server_response)
        client_socket.close()
    except OSError: # If the request is invalid or file not found, close the connection
        client_socket.close()


def get_status(server_response):
    buffer = server_response.split(b'\r\n')[0]
    status = buffer.split(b' ')[1]
    return status

# connection: close, the web server will close the connection after sending the response
def get_connection_close(server_response):
    connection = "connection: close" in server_response.decode().lower()
    return connection

def get_content_length(headers):
    lines = headers.split(b"\r\n")
    for line in lines:
        if line.lower().startswith(b"content-length"):
            length = line.split(b":")[1].strip()
            return int(length)
    return 0

# etag: entity tag, a unique identifier for a specific version of a resource, if the etag is the same, the resource is not changed
def get_etag(headers):
    lines = headers.split(b"\r\n")
    for line in lines:
        if b"if-none-match" in line.lower() or b"etag" in line.lower():
            etag = line.split(b":")[1].strip()
            return etag
    return b""

def get_server_response(host_name, request):
    # Connect to web server and send the request
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.connect((host_name, 80))
    server_socket.sendall(request)
    
    # Get the response from web server
    server_response = server_socket.recv(1024)

    # If the response is error code, return 403 Forbidden
    status = get_status(server_response)
    if status == b"100": # If the response is 100 continue, get the next response
        server_response = server_socket.recv(1024)

    # Get the header of the request
    chunked_encoding = False
    header_end = server_response.find(b"\r\n\r\n")
    headers = server_response[:header_end]
    
    # If the request is HEAD, return
    if b"HEAD" in request:
        server_socket.close()
        return server_response

    # If the response is "connection: close", get the response until the end of the response (the web server will closed eventually)
    if get_connection_close(headers):
        while True:
            data_chunk = server_socket.recv(1024)
            if data_chunk:
                server_response += data_chunk
            else:
                server_socket.close()
                return server_response

    # If the response is not "connection: close" and the body part is not empty, get the response by following the content length or chunked encoding 
    if get_etag(request) != get_etag(headers) or get_etag(request) == b"":
        chunked_encoding = "transfer-encoding: chunked" in headers.decode().lower()
        content_length = get_content_length(headers)
        # If the response is not chunked encoding, get the response by content length
        if not chunked_encoding and content_length > 0:
            if len(server_response) < header_end + 4 + content_length:
                length = content_length - (len(server_response) - header_end - 4)
                while len(server_response) < header_end + content_length + 4:
                    server_response += server_socket.recv(length)
        else:  # If the response is chunked encoding, get the response until meet '0' in the body part
            end_check = b'0'
            chunked_part = server_response.split(b"\r\n\r\n")[1]
            chunks = chunked_part.split(b"\r\n")
            if end_check not in chunks:
                while True:
                    data_chunk = server_socket.recv(1024)
                    server_response += data_chunk
                    data_chunks = data_chunk.split(b"\r\n")
                    if end_check in data_chunks:
                        break
            
    server_socket.close()
    return server_response

def get_image_data_response(host_name, request):
    server_response = get_server_response(host_name, request)
    # If the image response is error code, return empty image data
    if get_status(server_response) in error_codes:
        return b''
    
    # If the image response is not error code
    if "transfer-encoding: chunked" in server_response.split(b"\r\n\r\n")[0].decode().lower(): # If the image response is chunked encoding, get the image data from the chunks
        image_data = b""
        chunk_data = server_response.split(b"\r\n\r\n")[1]
        chunks = chunk_data.split(b"\r\n")
        for i in range(len(chunks)):
            if i % 2 == 1:
                image_data += chunks[i]
    else:
        image_data = server_response.split(b"\r\n\r\n")[1] # If the image response is not chunked encoding, get the image data from the body part
    return image_data

def cache_image(host_name, image_data, url):
    path = url.split(host_name)[1]
    img_ext = ""
    for ex in image_extensions:
        if ex in url:
            img_ext = ex
    file_name = "cache/" + host_name.replace(".", "dot=") + path.split(img_ext)[0].replace("?","qm=").replace("/","sla=").replace(".", "dot=").replace("#","sharp=") + img_ext
    # Save the image data to cache by the following file name in folder cache
    open(file_name, 'wb').write(image_data)
    # Update the cache time of the image
    images_cache_time[file_name[6:]] = time.time()
    # Announce the image is cached
    print('Image:', file_name, 'cached!')
        
def cache_clean():
    while True:
        # While multiple threads are running, sleep for CACHE_TIME seconds
        time.sleep(CACHE_TIME)
        print("Cache cleaning...")
        current_time = time.time()
        # Delete the image in cache folder if the image is not used for CACHE_TIME seconds
        for file in os.listdir("./cache"):
            if current_time - images_cache_time[file] > CACHE_TIME:
                print("Deleted", file)
                os.remove(os.path.join("cache/", file))
                recache_image(file) # Recache the image after deleting the image in cache folder by requesting the image to the web server again
        print("="*50)

def recache_image(file):
    file = file.replace("qm=","?").replace("dot=",".").replace("sla=","/").replace("sharp=","#")
    host_name = file.split('/')[0]
    paths = file.split('/')[1:]
    
    # Create the url to get the image
    url = "http://" + host_name
    for path in paths:
        url += "/" + path
        
    # Create the request to get the image
    request = f"GET {url} HTTP/1.1\r\nHost: {host_name}\r\n\r\n"
    # Send the request to web server and get the image data
    image_data = get_image_data_response(host_name,request.encode())
    # Cache the image data to cache folder
    cache_image(host_name, image_data, url)
    
def get_config():
    # Open the config file, get the cache time, white list and time limit from config file
    with open("config", "r") as file:
        for line in file:
            if "cache_time" in line:
                CACHE_TIME = float(line.split('=')[1].strip()) # Remove backspace, split the cache time by '=' and convert the cache time to float
            elif "whitelisting" in line:
                WHITE_LIST = line.split('=')[1].strip().split(', ') # Remove backspace and split the white list by ', '
            else:
                TIME_LIMIT = line.split('=')[1].strip().split('-') # Remove backspace and split the time limit by '-'
                TIME_LIMIT[0] = int(TIME_LIMIT[0])
                TIME_LIMIT[1] = int(TIME_LIMIT[1])
    return CACHE_TIME, WHITE_LIST, TIME_LIMIT

# Global variables
CACHE_TIME, WHITE_LIST, TIME_LIMIT = get_config()
WEB_CLIENT = 5
error_codes = [b'405', b'404', b'403', b'401', b'400', b'408', b'500', b'502', b'503']
image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico"]
images_cache_time = {}

def main():     
    # Validate command line arguments
    if len(sys.argv) <= 1:
        print('Usage : "python proxy.py [server_ip]"\n[server_ip : IP address of proxy server]')
        sys.exit(2)
    
    # Create a server socket, bind it to a port and start listening (allow at most WEB_CLIENT queued connections)
    tcpSerSock = socket(AF_INET, SOCK_STREAM) # AF_INET: IPv4, SOCK_STREAM: TCP (Transport layer protocol)
    tcpSerSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1) # SOL_SOCKET is the socket layer itself, SO_REUSEADDR is to reuse the socket address (IP of proxy server)
    tcpSerSock.bind((sys.argv[1], 8888)) # Input the IP of proxy server and port number 8888
    tcpSerSock.listen(WEB_CLIENT) # Allow at most WEB_CLIENT queued connections
    print('Proxy server is ready to receive connections...')

    # Create cache folder if not exists
    if not os.path.exists("./cache"):
        os.makedirs("./cache")
    else: # If cache folder exists, delete all the files in cache folder
        for file in os.listdir("./cache"):
            os.remove(os.path.join("./cache",file))
    
    # Create a thread to clean the cache folder once every CACHE_TIME seconds
    cache_clean_thread = threading.Thread(target=cache_clean, daemon=True)
    cache_clean_thread.start()
    
    # Main thread
    while True:
        try:
            print("Active threads:", threading.active_count())
            # Start receiving data from the web client
            print('Ready to serve...')
            tcpCliSock, addr = tcpSerSock.accept() # Accept a connection from web client
            print('Received a connection from:', addr)
            # Start a thread to handle mutiple requests from web client
            client_thread = threading.Thread(target=handle_client, args=(tcpCliSock,), daemon=False)
            client_thread.start()   
            print("="*50)
        except KeyboardInterrupt: # When Ctrl + C is pressed, close the connection from web client to proxy server and exit
            print("Exiting program...")
            break
    tcpSerSock.close()

    print("Active threads:", threading.active_count())
    
main()
