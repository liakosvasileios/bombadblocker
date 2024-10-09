
# DNS Server with DNS-over-HTTPS (DoH) Support and Domain Blocking

This project is a DNS server that supports DNS-over-HTTPS (DoH) for secure DNS resolution and allows blocking specific domains, such as ads or malicious websites. The server also caches DNS responses to improve performance and supports multithreading for handling multiple DNS requests concurrently.

## Features

- **DNS-over-HTTPS (DoH):** The server forwards DNS queries to a DoH server (supports multiple DoH servers including Cloudflare and Google by default) for secure and private DNS resolution.
- **Domain Blocking:** The server blocks domains listed in the `blocked_list.txt` file, returning `0.0.0.0` for blocked domains.
- **Caching:** Resolved IP addresses are cached to speed up responses to repeated queries. Cache entries are valid for a configurable time-to-live (TTL).
- **Multithreading:** DNS requests are handled in separate threads, allowing the server to process multiple queries concurrently.
- **Configurable Settings:** Includes a `config.json` file where you can specify various settings like cache TTL, the number of workers, and DoH servers.

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

### Configuration File (`config.json`)

You can configure various settings for the DNS server using the `config.json` file. If the file is missing or empty, default values will be used.

Example `config.json`:

\`\`\`json
{
  "max_workers": 100,
  "cache_ttl": 60,
  "blocked_domains_file": "blocked_list.txt",
  "doh_servers": [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/dns-query"
  ]
}
\`\`\`

- **max_workers**: The maximum number of threads for handling DNS requests.
- **cache_ttl**: Time-to-live (in seconds) for cached DNS responses.
- **blocked_domains_file**: Path to the file containing the list of blocked domains.
- **doh_servers**: List of DoH servers that the server can randomly select for resolving DNS queries.

### Usage

1. Clone or download the repository.
2. Install the required Python libraries as mentioned above.
3. Run the DNS server with:

   \`\`\`bash
   python server.py
   \`\`\`

4. The DNS server will start on the local IP address of the machine on port 53 by default.

### Configuration

- **Port**: The server defaults to port 53. You can change this by modifying the `start_dns_server()` function call in the script.
- **DoH Server**: The script uses Cloudflare's and Google's DoH servers. You can add or modify the servers in the `config.json` file.

### Example Workflow

1. The server receives a DNS request.
2. It checks if the domain is in the blocklist. If yes, it replies with `0.0.0.0`.
3. If the domain is not blocked, the server checks the cache. If a valid cached response exists, it serves the response from the cache.
4. If there is no cached response, the request is forwarded to a randomly selected DoH server for resolution.
5. The response is cached and sent back to the client.

## Code Structure

- `load_blocked_domains(file_path)`: Loads the blocked domains from a text file.
- `is_blocked(domain)`: Checks if a domain is in the blocklist.
- `resolve_from_cache(domain)`: Checks if a domain's IP address is cached.
- `cache_response(domain, ip)`: Caches the response for a domain.
- `query_doh_server(request_data)`: Sends the DNS query to a DoH server and returns the response.
- `handle_dns_request(data, client_addr, sock)`: Processes incoming DNS requests, checks the blocklist and cache, and forwards the request to a DoH server if necessary.
- `start_dns_server(host, port)`: Starts the DNS server on the specified host and port.

## New Features

- **Timestamps**: Logs now include timestamps to track events more accurately.
- **Configurable DoH Servers**: The server can now use multiple DoH servers (Cloudflare and Google by default). These are randomly selected for each query.
- **Error Handling**: The server handles empty or missing configuration files and provides appropriate error messages.

## Troubleshooting

- **OSError: [Errno 98] Address already in use**: Make sure no other process is using port 53. 
