"""TLS context construction shared by the server and client."""
import ssl


def server_context(certfile, keyfile):
    if not certfile or not keyfile:
        raise ValueError("Both a TLS certificate and private key are required.")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile, keyfile)
    return context


def client_context(cafile=None):
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile or None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
