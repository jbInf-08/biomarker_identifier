Optional TLS for nginx (when you add a listen 443 ssl server block in nginx.prod.conf):

  fullchain.pem  — server certificate chain
  privkey.pem    — private key

For local testing, use mkcert or a self-signed pair. In production, prefer TLS at
your cloud load balancer and keep nginx on HTTP behind a private network.
