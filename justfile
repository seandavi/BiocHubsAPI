# Bioconductor Hubs API - Task Runner
# https://github.com/casey/just

#   ✅ Complete Workflows
#   just setup          # Build → Deploy → Init DB (one command!)
#   just migrate        # Copy SQLite → Run migration → Show stats
#   just redeploy       # Rebuild image → Restart pods
#   just reset          # Clean → Deploy → Init (fresh start)

#   ✅ Smarter Commands
#   just sql "SELECT COUNT(*) FROM resources"  # Execute SQL directly
#   just scale 5                               # Scale to 5 replicas
#   just port-forward 8080                     # Custom port
#   just copy-sqlite my-ah.db my-eh.db        # Custom file names

#   ✅ Developer-Friendly
#   just dev            # Local dev server with reload
#   just fmt            # Format code
#   just lint           # Run linters
#   just test           # Run tests

#   ✅ Better Defaults & Safety
#   - Default values for all parameters
#   - Confirmation prompts for destructive operations
#   - Better error messages
#   - No tab/space confusion

#   Quick Reference

#   # Most common commands
#   just                 # List all recipes
#   just setup           # Complete first-time setup
#   just deploy          # Deploy to K8s
#   just logs            # Watch logs
#   just shell-api       # Shell into pod
#   just stats           # DB statistics
#   just port-forward    # Access API locally


# Configuration
image_name := "biochubs-api"
image_tag := "latest"
namespace := "biochubs"

# Default recipe (runs when you type 'just')
default:
    @just --list

# ============================================================================
# Docker
# ============================================================================

# Build Docker image
build:
    docker build -t {{image_name}}:{{image_tag}} .

# Build and show image info
build-info: build
    @echo "Image built successfully!"
    docker images {{image_name}}:{{image_tag}}
    @echo ""
    docker history {{image_name}}:{{image_tag}} --no-trunc

# Run container locally (requires POSTGRES_URI env var)
run-local port="8000":
    #!/usr/bin/env bash
    if [ -z "$POSTGRES_URI" ]; then
        echo "Error: POSTGRES_URI environment variable not set"
        echo "Example: export POSTGRES_URI=postgresql://postgres:password@localhost:5432/hubs_dev"
        exit 1
    fi
    docker run --rm -p {{port}}:8000 -e POSTGRES_URI=$POSTGRES_URI {{image_name}}:{{image_tag}}

# Push image to registry (update with your registry)
push registry="ghcr.io/yourusername":
    @echo "Pushing to {{registry}}/{{image_name}}:{{image_tag}}"
    docker tag {{image_name}}:{{image_tag}} {{registry}}/{{image_name}}:{{image_tag}}
    docker push {{registry}}/{{image_name}}:{{image_tag}}

# ============================================================================
# Kubernetes Deployment
# ============================================================================

# Deploy all Kubernetes resources
deploy:
    @echo "Deploying to Kubernetes namespace: {{namespace}}"
    kubectl apply -f k8s/namespace.yaml
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secret.yaml
    kubectl apply -f k8s/postgres-statefulset.yaml
    kubectl apply -f k8s/api-deployment.yaml
    kubectl apply -f k8s/api-service.yaml
    @echo ""
    @echo "Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n {{namespace}} --timeout=120s
    @echo "Waiting for API to be ready..."
    kubectl wait --for=condition=ready pod -l app=biochubs-api -n {{namespace}} --timeout=120s
    @echo ""
    @echo "✓ Deployment complete!"
    @just status

# Deploy ingress controller (optional)
deploy-ingress:
    kubectl apply -f k8s/ingress.yaml

# Delete all Kubernetes resources
clean:
    @echo "⚠️  This will delete the entire namespace and all data!"
    @echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
    kubectl delete namespace {{namespace}}

# Restart API deployment
restart-api:
    kubectl rollout restart deployment/biochubs-api -n {{namespace}}
    @echo "Waiting for rollout to complete..."
    kubectl rollout status deployment/biochubs-api -n {{namespace}}

# Restart PostgreSQL
restart-db:
    kubectl rollout restart statefulset/postgres -n {{namespace}}

# Scale API deployment
scale replicas:
    kubectl scale deployment biochubs-api -n {{namespace}} --replicas={{replicas}}
    @echo "Scaled to {{replicas}} replicas"
    @sleep 2
    @just status

# ============================================================================
# Monitoring & Logs
# ============================================================================

# Show deployment status
status:
    @echo "=== Namespace ==="
    kubectl get namespace {{namespace}}
    @echo ""
    @echo "=== Pods ==="
    kubectl get pods -n {{namespace}}
    @echo ""
    @echo "=== Services ==="
    kubectl get svc -n {{namespace}}
    @echo ""
    @echo "=== PersistentVolumeClaims ==="
    kubectl get pvc -n {{namespace}}

# Describe all resources
describe:
    kubectl describe all -n {{namespace}}

# Show API logs (follow mode)
logs:
    kubectl logs -n {{namespace}} -l app=biochubs-api --tail=100 -f

# Show PostgreSQL logs (follow mode)
logs-db:
    kubectl logs -n {{namespace}} -l app=postgres --tail=100 -f

# Show recent API logs (last 100 lines)
logs-tail lines="100":
    kubectl logs -n {{namespace}} -l app=biochubs-api --tail={{lines}}

# Show resource usage
top:
    @echo "=== Pod Resource Usage ==="
    kubectl top pods -n {{namespace}}
    @echo ""
    @echo "=== Node Resource Usage ==="
    kubectl top nodes

# Watch pods in real-time
watch:
    watch kubectl get pods -n {{namespace}}

# ============================================================================
# Database Management
# ============================================================================

# Initialize database schema
init-db:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    echo "Initializing database in pod $POD..."
    kubectl exec -n {{namespace}} $POD -- uv run hubs-api db init

# Run database migration (requires SQLite files in pod)
migrate-db:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    echo "Running migration in pod $POD..."
    kubectl exec -n {{namespace}} $POD -- uv run hubs-api db migrate

# Show database statistics
stats:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    kubectl exec -n {{namespace}} $POD -- uv run hubs-api db stats

# Backup PostgreSQL database
backup-db:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=postgres -o jsonpath='{.items[0].metadata.name}')
    BACKUP_FILE="backup-$(date +%Y%m%d-%H%M%S).sql"
    echo "Backing up to $BACKUP_FILE..."
    kubectl exec -n {{namespace}} $POD -- pg_dump -U postgres hubs_dev > $BACKUP_FILE
    echo "✓ Backup complete: $BACKUP_FILE"

# Restore PostgreSQL database from backup file
restore-db backup_file:
    #!/usr/bin/env bash
    if [ ! -f "{{backup_file}}" ]; then
        echo "Error: Backup file {{backup_file}} not found"
        exit 1
    fi
    POD=$(kubectl get pods -n {{namespace}} -l app=postgres -o jsonpath='{.items[0].metadata.name}')
    echo "Restoring from {{backup_file}} to pod $POD..."
    kubectl exec -i -n {{namespace}} $POD -- psql -U postgres hubs_dev < {{backup_file}}
    echo "✓ Restore complete"

# ============================================================================
# Shell Access
# ============================================================================

# Open shell in API pod
shell-api:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    echo "Opening shell in $POD..."
    kubectl exec -it -n {{namespace}} $POD -- /bin/sh

# Open psql shell in PostgreSQL pod
shell-db:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=postgres -o jsonpath='{.items[0].metadata.name}')
    echo "Opening psql in $POD..."
    kubectl exec -it -n {{namespace}} $POD -- psql -U postgres -d hubs_dev

# Execute SQL query in PostgreSQL
sql query:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=postgres -o jsonpath='{.items[0].metadata.name}')
    kubectl exec -n {{namespace}} $POD -- psql -U postgres -d hubs_dev -c "{{query}}"

# ============================================================================
# Port Forwarding
# ============================================================================

# Forward API port to localhost
port-forward port="8000":
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    echo "Forwarding http://localhost:{{port}} to $POD..."
    echo "API Docs: http://localhost:{{port}}/docs"
    kubectl port-forward -n {{namespace}} $POD {{port}}:8000

# Forward PostgreSQL port to localhost
port-forward-db port="5432":
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=postgres -o jsonpath='{.items[0].metadata.name}')
    echo "Forwarding localhost:{{port}} to PostgreSQL in $POD..."
    kubectl port-forward -n {{namespace}} $POD {{port}}:5432

# ============================================================================
# File Operations
# ============================================================================

# Copy SQLite files to API pod for migration
copy-sqlite ah_file="annotationhub.sqlite3" eh_file="experimenthub.sqlite3":
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    echo "Copying SQLite files to $POD:/tmp/"
    kubectl cp {{ah_file}} {{namespace}}/$POD:/tmp/annotationhub.sqlite3
    kubectl cp {{eh_file}} {{namespace}}/$POD:/tmp/experimenthub.sqlite3
    echo "✓ Files copied. Run: just migrate-db"

# Copy file to API pod
copy-to-api local_file remote_path:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    kubectl cp {{local_file}} {{namespace}}/$POD:{{remote_path}}

# Copy file from API pod
copy-from-api remote_path local_file:
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    kubectl cp {{namespace}}/$POD:{{remote_path}} {{local_file}}

# ============================================================================
# Development
# ============================================================================

# Run local development server (no Docker)
dev:
    uv run hubs-api serve --reload

# Run tests (when implemented)
test:
    uv run pytest

# Format code
fmt:
    uv run ruff format src/
    uv run ruff check --fix src/

# Lint code
lint:
    uv run ruff check src/

# ============================================================================
# Complete Workflows
# ============================================================================

# Complete setup: build, deploy, and initialize database
setup: build deploy init-db
    @echo ""
    @echo "✓ Complete setup finished!"
    @echo ""
    @echo "Access the API:"
    @echo "  just port-forward"
    @echo "  Then visit: http://localhost:8000/docs"

# Complete migration workflow
migrate ah_file="annotationhub.sqlite3" eh_file="experimenthub.sqlite3": (copy-sqlite ah_file eh_file) migrate-db
    @echo "✓ Migration complete!"
    @just stats

# Rebuild and redeploy
redeploy: build restart-api
    @echo "✓ Redeployed with new image"

# Full cleanup and fresh deploy
reset: clean deploy init-db
    @echo "✓ Fresh deployment complete!"

# ============================================================================
# Health Checks
# ============================================================================

# Check if API is healthy
health-check:
    #!/usr/bin/env bash
    SVC=$(kubectl get svc -n {{namespace}} biochubs-api-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -z "$SVC" ]; then
        echo "Using port-forward for health check..."
        POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
        kubectl port-forward -n {{namespace}} $POD 8888:8000 &
        PF_PID=$!
        sleep 2
        curl -s http://localhost:8888/health | jq .
        kill $PF_PID
    else
        curl -s http://$SVC/health | jq .
    fi

# Test API endpoint
test-api endpoint="/":
    #!/usr/bin/env bash
    POD=$(kubectl get pods -n {{namespace}} -l app=biochubs-api -o jsonpath='{.items[0].metadata.name}')
    kubectl port-forward -n {{namespace}} $POD 8888:8000 &
    PF_PID=$!
    sleep 2
    curl -s http://localhost:8888{{endpoint}} | jq .
    kill $PF_PID
