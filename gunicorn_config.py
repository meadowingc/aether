bind = "127.0.0.1:34782"
workers = 1
threads = 8
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Enable logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Performance tuning
worker_class = "gthread"  # Use threading worker
worker_connections = 1000
