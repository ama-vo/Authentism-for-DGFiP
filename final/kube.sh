#/bin/bash

# faire source ./kube.sh

export KUBECONFIG=/home/krawlyag/.kube/local.yaml  

kubectl port-forward svc/web 8080:80 -n n-grp4 --insecure-skip-tls-verify

