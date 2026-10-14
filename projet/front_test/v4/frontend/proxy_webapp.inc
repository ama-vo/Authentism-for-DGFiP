# Relais vers l'Application Web en HTTPS, certificat vérifié contre l'AC
# interne (PKI). X-Real-IP est TOUJOURS écrasé par l'IP vue par Nginx :
# le client ne peut pas usurper son adresse dans les journaux.
proxy_pass https://webapp_pool;
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
proxy_ssl_trusted_certificate /pki/edge/ca.crt;
proxy_ssl_verify on;
proxy_ssl_verify_depth 2;
proxy_ssl_name webapp;
proxy_ssl_server_name on;
proxy_ssl_session_reuse on;
proxy_connect_timeout 5s;
proxy_read_timeout 15s;
proxy_next_upstream error timeout http_502 http_503;
