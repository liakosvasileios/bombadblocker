
# DNS Server with DNS-over-HTTPS (DoH) Support and Domain Blocking

This project is a DNS server that supports DNS-over-HTTPS (DoH) for resolving domain names and allows blocking specific domains (such as ads or malicious websites). It features a simple cache for speeding up responses to repeated queries and blocks specific domains as specified in a blocklist file.

## Features

- **DNS-over-HTTPS (DoH):** The server forwards DNS queries to a DoH server (Cloudflare's DoH by default) for secure and private DNS resolution.
- **Domain Blocking:** The server blocks domains listed in the `blocked_list.txt` file, returning `0.0.0.0` for those domains.
- **Caching:** Resolved IP addresses are cached to improve performance. Cache entries are valid for a configurable time-to-live (TTL).
- **Multithreading:** DNS requests are handled in separate threads, allowing for concurrent processing of multiple queries.

## Installation and Setup

### Prerequisites

- Python 3.x
- Required libraries: Install them using the following command:

  \`\`\`bash
  pip install dnslib requests
  \`\`\`

### Blocklist Configuration

- Create a file named `blocked_list.txt` in the same directory as the server script.
- Add one domain per line that you wish to block.

Example `blocked_list.txt`:

\`\`\`
example.com
ads.example.com
tracking.example.net
\`\`\`

### Usage

1. Clone or download the repository.
2. Install the required Python libraries as mentioned above.
3. Run the DNS server with:

   \`\`\`bash
   sudo python3 server.py
   \`\`\`

4. The DNS server will start on the local IP address of the machine on port 53 by default.

### Configuration

- **Port**: The server defaults to port 53. You can change this by modifying the `start_dns_server()` function call in the script.
- **DoH Server**: The script uses Cloudflare's DoH server (`https://cloudflare-dns.com/dns-query`). You can change this by updating the `DOH_SERVER` variable.

### Example Workflow

1. The server receives a DNS request.
2. It checks if the domain is in the blocklist. If yes, it replies with `0.0.0.0`.
3. If the domain is not blocked, the server checks the cache. If a valid cached response exists, it serves the response from the cache.
4. If there is no cached response, the request is forwarded to the DoH server for resolution.
5. The response is cached and sent back to the client.

## Code Structure

- `load_blocked_domains(file_path)`: Loads the blocked domains from a text file.
- `is_blocked(domain)`: Checks if a domain is in the blocklist.
- `resolve_from_cache(domain)`: Checks if a domain's IP address is cached.
- `cache_response(domain, ip)`: Caches the response for a domain.
- `query_doh_server(request_data)`: Sends the DNS query to the DoH server and returns the response.
- `handle_dns_request(data, client_addr, sock)`: Processes incoming DNS requests, checks the blocklist and cache, and forwards to the DoH server if necessary.
- `start_dns_server(host, port)`: Starts the DNS server on the specified host and port.

## Troubleshooting

- In case of OSError, you should terminate every other process using port 53.
