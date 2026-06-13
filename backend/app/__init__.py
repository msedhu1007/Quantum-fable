# Use the OS trust store (macOS keychain / Windows store) for TLS verification so
# corporate-proxy CA certificates work. Must run before any httpx/anthropic client
# is constructed — providers create module-level clients on import.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass
