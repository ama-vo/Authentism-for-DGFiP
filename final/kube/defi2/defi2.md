
export KUBECONFIG= ...


kubectl get pods --insecure-skip-tls-verify -n n-grp4

kubectl apply -f ./.kube/defi2-service.yaml --insecure-skip-tls-verify -n n-grp4

# 1 par terminal

kubectl proxy --kubeconfig=./.kube/local.yaml --insecure-skip-tls-verify
