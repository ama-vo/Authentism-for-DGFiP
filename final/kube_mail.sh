#/bin/bash

# faire source ./kube_mail.sh

export KUBECONFIG=/home/krawlyag/.kube/local.yaml  

kubectl port-forward svc/mail 8025:8025 -n n-grp4 --insecure-skip-tls-verify
