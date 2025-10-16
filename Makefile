.PHONY: help build push deploy clean logs status init-db migrate-db

# Configuration
IMAGE_NAME := biochubs-api
IMAGE_TAG := latest
NAMESPACE := biochubs

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

push: ## Push image to registry (update with your registry)
	@echo "Update this target with your registry URL"
	# docker tag $(IMAGE_NAME):$(IMAGE_TAG) your-registry/$(IMAGE_NAME):$(IMAGE_TAG)
	# docker push your-registry/$(IMAGE_NAME):$(IMAGE_TAG)

deploy: ## Deploy to Kubernetes
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/secret.yaml
	kubectl apply -f k8s/postgres-statefulset.yaml
	kubectl apply -f k8s/api-deployment.yaml
	kubectl apply -f k8s/api-service.yaml
	@echo "Waiting for pods to be ready..."
	kubectl wait --for=condition=ready pod -l app=postgres -n $(NAMESPACE) --timeout=120s
	kubectl wait --for=condition=ready pod -l app=biochubs-api -n $(NAMESPACE) --timeout=120s
	@echo "Deployment complete!"

deploy-ingress: ## Deploy ingress (optional)
	kubectl apply -f k8s/ingress.yaml

clean: ## Delete all Kubernetes resources
	kubectl delete namespace $(NAMESPACE)

logs: ## Show API logs
	kubectl logs -n $(NAMESPACE) -l app=biochubs-api --tail=100 -f

logs-db: ## Show PostgreSQL logs
	kubectl logs -n $(NAMESPACE) -l app=postgres --tail=100 -f

status: ## Show deployment status
	@echo "=== Namespace ==="
	kubectl get namespace $(NAMESPACE)
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods -n $(NAMESPACE)
	@echo ""
	@echo "=== Services ==="
	kubectl get svc -n $(NAMESPACE)
	@echo ""
	@echo "=== PersistentVolumeClaims ==="
	kubectl get pvc -n $(NAMESPACE)

describe: ## Describe all resources
	kubectl describe all -n $(NAMESPACE)

shell-api: ## Open shell in API pod
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -it -n $(NAMESPACE) $$POD -- /bin/sh

shell-db: ## Open psql in PostgreSQL pod
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=postgres -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -it -n $(NAMESPACE) $$POD -- psql -U postgres -d hubs_dev

init-db: ## Initialize database schema
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}'); \
	echo "Initializing database in pod $$POD..."; \
	kubectl exec -n $(NAMESPACE) $$POD -- uv run hubs-api db init

migrate-db: ## Run database migration (requires SQLite files in pod)
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}'); \
	echo "Running migration in pod $$POD..."; \
	kubectl exec -n $(NAMESPACE) $$POD -- uv run hubs-api db migrate

stats: ## Show database statistics
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -n $(NAMESPACE) $$POD -- uv run hubs-api db stats

scale: ## Scale API deployment (usage: make scale REPLICAS=3)
	kubectl scale deployment biochubs-api -n $(NAMESPACE) --replicas=$(REPLICAS)

restart-api: ## Restart API pods
	kubectl rollout restart deployment/biochubs-api -n $(NAMESPACE)

restart-db: ## Restart PostgreSQL pod
	kubectl rollout restart statefulset/postgres -n $(NAMESPACE)

backup-db: ## Backup PostgreSQL database
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=postgres -o jsonpath='{.items[0].metadata.name}'); \
	BACKUP_FILE=backup-$$(date +%Y%m%d-%H%M%S).sql; \
	echo "Backing up to $$BACKUP_FILE..."; \
	kubectl exec -n $(NAMESPACE) $$POD -- pg_dump -U postgres hubs_dev > $$BACKUP_FILE; \
	echo "Backup complete: $$BACKUP_FILE"

top: ## Show resource usage
	kubectl top pods -n $(NAMESPACE)
	kubectl top nodes

port-forward: ## Forward API port to localhost:8000
	@echo "API will be available at http://localhost:8000"
	@POD=$$(kubectl get pods -n $(NAMESPACE) -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}'); \
	kubectl port-forward -n $(NAMESPACE) $$POD 8000:8000
