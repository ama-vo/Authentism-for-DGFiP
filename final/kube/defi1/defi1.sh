#/bin/bash

# a changer au besoin (et faire un source)
export KUBECONFIG=/home/krawlyag/.kube/local.yaml 


kubectl create deployment test1-defi1 --image=xhelozs/csc8567:v1 --insecure-skip-tls-verify -n n-grp4

kubectl port-forward pods/test1-defi1-598d779785-54tzj 8082:5000 --insecure-skip-tls-verify -n n-grp4

