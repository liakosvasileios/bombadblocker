import base64
import socket
import requests
from dnslib import DNSRecord, QTYPE, RR, A
import time
import concurrent.futures
from datetime import datetime
import json
from rapidfuzz import fuzz
from collections import defaultdict

# Load config from JSON file
def load_config(config_file='config.json'):
    try:
        with open(config_file, 'r') as file:
            config_data = file.read().strip()
            if not config_data:  # Handle empty file
                raise ValueError("Config file is empty")
            return json.loads(config_data)
    except FileNotFoundError:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Config file '{config_file}' not found. Using defaults.")
        return {}
    except ValueError as ve:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error in config file: {ve}. Using defaults.")
        return {}
        


config = load_config()

executor = concurrent.futures.ThreadPoolExecutor(max_workers=config.get('max_workers', 100))

# Dictionary to track requests (client_ip -> (request_count, first_request_time))
request_counts = defaultdict(lambda: [0, time.time()])

# Blocked domains will be loaded from the file
BLOCKED_DOMAINS = set()
# Trusted domains will be loaded from the file
TRUSTED_DOMAINS = set()

def load_blocked_domains(file_path=config.get('blocked_domains_file', 'blocked_list.txt')):
    try:
        with open(file_path, 'r') as file:
            for line in file:
                domain = line.strip()
                if domain:
                    BLOCKED_DOMAINS.add(domain)
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Loaded {len(BLOCKED_DOMAINS)} blocked domains.")
    except FileNotFoundError:
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Blocklist file '{file_path}' not found. No domains are blocked.")



def load_trusted_domains(file_path=config.get('trusted_domains_file', 'trusted_list.txt')):
    try:
        with open(file_path, 'r') as file:
            for line in file:
                domain = line.strip()
                if domain:
                    TRUSTED_DOMAINS.add(domain)
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Loaded {len(TRUSTED_DOMAINS)} trusted domains.")
    except FileNotFoundError:
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Trusted domains list file '{file_path}' not found. Ignoring...")


# Cache dictionary (domain -> IP, expiration_time)
CACHE = {}

# DNS Cache time-to-live (sec)
CACHE_TTL = config.get('cache_ttl', 60)

# Check if a domain is in the blacklist
def is_blocked(domain):
    return domain in BLOCKED_DOMAINS


def resolve_from_cache(domain):
    # if domain is in cache and is still valid
    if domain in CACHE and CACHE[domain][1] > time.time():
        return CACHE[domain][0]
    return None


def cache_response(domain, ip):
    # Check if the IP is valid before caching
    if is_blocked(domain):
        # Do not cache blocked domains
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Not caching blocked domain: {domain}")
        return
    try:
        socket.inet_aton(ip)
        CACHE[domain] = (ip, time.time() + CACHE_TTL)
    except socket.error:
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Invalid IP address '{ip}' for domain '{domain}'. Not caching.")


                                
# List of DoH servers
DOH_SERVERS = config.get('doh_servers', [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query"
])

# DoH headers configuration
DOH_HEADERS = {
    'Content-Type': 'application/dns-message',
    'Accept': 'application/dns-message'
}


def query_doh_server(request_data):
    # Pick a random DoH server from the list
    doh_server = random.choice(DOH_SERVERS)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Querying DoH server: {doh_server}")
    try:
        doh_query = base64.urlsafe_b64encode(request_data).decode('utf-8')
        response = requests.get(f'{doh_server}?dns={doh_query}', headers=DOH_HEADERS)

        if response.status_code == 200:
            return response.content
        else:
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] DoH query failed with status: {response.status_code}')
    except Exception as e:
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] DoH query error: {e}')
    return None


def handle_dns_request(data, client_addr, sock):
    # Check rate limiting
    if is_rate_limited(client_addr[0]):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Rate limit exceeded for {client_addr[0]}.")
        # Respond with a custom message or DNS error
        reply = DNSRecord.answer()  # This can be a custom error response
        sock.sendto(reply.pack(), client_addr)
        return

    request = DNSRecord.parse(data)
    qname = str(request.q.qname).strip('.')

    # LOGGING
    log_dns_query(qname, client_addr[0])

    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Received DNS request for: {qname}')

    if is_blocked(qname):
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Blocking domain: {qname}')
        reply = request.reply()
        reply.add_answer(RR(qname, QTYPE.A, rdata=A('0.0.0.0'), ttl=60))
        sock.sendto(reply.pack(), client_addr)
        return

    cached_ip = resolve_from_cache(qname)
    if cached_ip:
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Serving {qname} from cache')
        try:
            reply = request.reply()
            reply.add_answer(RR(qname, QTYPE.A, rdata=A(cached_ip), ttl=60))
            sock.sendto(reply.pack(), client_addr)
            return
        except ValueError as e:
            print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Error serving {qname} from cache: {e}")
            return 

    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Forwarding {qname} to DoH server')
    upstream_response = query_doh_server(data)

    if upstream_response:
        upstream_dns_response = DNSRecord.parse(upstream_response)
        if upstream_dns_response.rr:
            answer = upstream_dns_response.rr[0].rdata
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Caching response: {qname} -> {answer}')
            cache_response(qname, str(answer))
        # Send the response to the original client
        sock.sendto(upstream_response, client_addr)
    else:
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Failed to get upstream response for {qname}, sending error response")
        # Optionally send an error response or simply ignore


    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Forwarding {qname} to DoH server')
    upstream_response = query_doh_server(data)
    # Cache response
    if upstream_response:
        upstream_dns_response = DNSRecord.parse(upstream_response)
        if upstream_dns_response.rr:
            answer = upstream_dns_response.rr[0].rdata
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Caching response: {qname} -> {answer}')
            cache_response(qname, str(answer))

    # Send the response to the original client
    sock.sendto(upstream_response, client_addr)


def get_local_ip():
    try:
        # Create a temporary socket to determine the IP address
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect(('8.8.8.8', 80))  # Connecting to an external address (Google's DNS)
        local_ip = temp_sock.getsockname()[0]
        temp_sock.close()
        return local_ip
    except Exception as e:
        print(f"[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Error retrieving local IP: {e}")
        return '127.0.0.1'  # Default to localhost if there's an error


def is_phishing_domain(domain, trusted_domains=None):
    if trusted_domains is None:
        trusted_domains = TRUSTED_DOMAINS

    # Convert domain to lowercase for case-insensitive comparison
    domain = domain.lower()

    for trusted in trusted_domains:
        # Check for exact match first to avoid unnecessary computation
        if domain == trusted.lower():
            return False  # Domain is trusted, no phishing detected

        # Use fuzz ratio to detect phishing-like domains
        similarity = fuzz.ratio(domain, trusted.lower())
        if similarity > 80:  # Set a threshold for phishing detection
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Detected potential phishing domain: {domain}")
            return True

    return False


def log_dns_query(domain, client_ip, log_file='dns_queries.log'):
    log_entry = {
        "domain": domain,
        "client_ip": client_ip,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    try:
        with open(log_file, 'a') as logfile:
            logfile.write(json.dumps(log_entry) + "\n")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Logged DNS query: {domain} from {client_ip}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to log DNS query: {e}")


def is_rate_limited(client_ip):
    current_time = time.time()
    request_count, first_request_time = request_counts[client_ip]

    # Check if the time window has expired
    if current_time - first_request_time > config.get('time_window'):
        # Reset the count and time
        request_counts[client_ip] = [1, current_time]
        return False  # Not rate limited
    else:
        # Within the time window
        if request_count < config.get('rate_limit'):
            # Increment the count
            request_counts[client_ip][0] += 1
            return False  # Not rate limited
        else:
            return True  # Rate limited


def start_dns_server(host, port=53):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] DNS server started on {host}:{port}. Bomba.')

    while True:
        try: 
            data, client_addr = sock.recvfrom(512)
            executor.submit(handle_dns_request, data, client_addr, sock)
        except Exception as e:
            print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Error handling DNS request: {e}')


if __name__ == '__main__':
    host_addr = get_local_ip()
    load_blocked_domains()
    start_dns_server(host_addr)