# Part 3: Infrastructure as Code (AWS)

This directory contains Terraform to deploy the **Part 2 FastAPI service** to AWS using **ECS Fargate**, **ALB**, **API Gateway (HTTP API + VPC Link)**, **CloudWatch logs/alarms**, **IAM**, and **RDS Postgres** (provisioned to satisfy the requirement).

## Execution status (what I actually ran)
Because I do **not** have an AWS account/credentials in this environment, I did **not** run `terraform plan` or `terraform apply`.

I **did** run locally (no AWS required):
- `terraform init`
- `terraform fmt -recursive`
- `terraform validate`

A reviewer can provide AWS credentials and run `terraform init/plan/apply` as described below.

---

## Relationship to Part 2
- **Part 2** implements the service logic and runs locally using **SQLite (embedded DB)**.
- **Part 3** provides production-oriented cloud infrastructure to deploy the same service as a container.
- **RDS Postgres is provisioned** to meet the “RDS or DynamoDB” requirement and represent a production datastore. The current container still uses SQLite via `DB_PATH` unless the app is extended to use Postgres.

Containerization artifacts (ECS packaging):
- `Dockerfile` and `.dockerignore` at repo root build the container image consumed by the ECS task definition.
- Docker is **not required** to run Part 2 locally (venv + SQLite is the primary dev workflow).
- Docker is **required** only if you are building/pushing an image for ECS (see Deployment guide 0 below).
- For an optional local container smoke test, see **README.md → “Containerization (Docker)”**.

IaC code is under `infra/terraform/`.

---

## What this deploys (high level)
Traffic Flow
```
Internet → API Gateway (public) → VPC Link → Internal ALB (private) → ECS Tasks (public)
```
Terraform under `infra/terraform/` creates:

- Networking:
  - VPC + **public subnets** (for ECS tasks and VPC Link) + **private subnets** (for ALB)
  - Internet Gateway + route tables

- Compute:
  - ECS cluster
  - ECS Fargate task definition + service

- Traffic ingress:
  - **Internal ALB** (private subnets, only accessible via API Gateway VPC Link)
  - Target group health check: `GET /api/v1/health`
  - **API Gateway HTTP API** → **VPC Link** → Internal ALB integration
  - **Security**: ALB security group restricts ingress to API Gateway VPC Link only

- Data:
  - **RDS Postgres** instance (minimal sizing) + subnet group + security group

- Observability:
  - CloudWatch log group for container logs
  - CloudWatch alarms (ECS CPU/memory, ALB 5xx, RDS CPU/storage)

- IAM:
  - ECS execution role + task role
  - Optional CodeDeploy role/resources (blue/green)

- Scaling:
  - ECS Service autoscaling via target tracking (CPU/memory)

---

## Prerequisites

### Local tools
- Terraform (>= 1.5)
- AWS CLI v2
- Docker

### AWS access
To run `plan/apply`, you need:
- An AWS account with billing enabled
- Credentials configured locally (Access keys / SSO / role)
- Permissions to create: VPC, ECS, ECR, ALB, API Gateway, CloudWatch, IAM, RDS

Validate credentials:
```bash
aws sts get-caller-identity
```

---

## Deployment guide

### 0) Build and push the container image (ECR example)
To deploy to ECS, you must build a container image (using the repo-root `Dockerfile`) and push it to a registry (ECR shown here). Then set `container_image` to that image URI.

Prerequisites for this step:
- Docker installed/running (Docker Desktop on macOS)
- AWS account + credentials configured locally
- AWS CLI installed (`aws`)
- Permissions to create/push to ECR

```bash
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO_NAME=knwl-platform

aws ecr create-repository --repository-name "$REPO_NAME" --region "$AWS_REGION" 2>/dev/null || true

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

IMAGE_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO_NAME:latest"

# From repo root (where Dockerfile is)
docker build -t "$REPO_NAME:latest" .
docker tag "$REPO_NAME:latest" "$IMAGE_URI"
docker push "$IMAGE_URI"

echo "IMAGE_URI=$IMAGE_URI"
```

### 1) Create your Terraform variables file
Copy the example and fill in real values:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Minimum variables to set correctly:
- `container_image` (use your actual ECR URI)
- `db_password` (use a strong password)

### 2) Terraform apply
```bash
cd infra/terraform
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

### 3) Verify deployment
Terraform outputs should include:
- API Gateway base URL (recommended entry point - use this for all access)
- ALB DNS name (internal only, not directly accessible from internet)

**Note**: The ALB is internal and can only be accessed via API Gateway. Direct access to the ALB DNS name will not work from outside the VPC.

Verify health via API Gateway URL:
```bash
curl -i <APIGW_URL>/api/v1/health
```

---

## Security Architecture

### Network Security
- **ALB**: Internal load balancer in private subnets
  - Security group restricts ingress to API Gateway VPC Link only
  - Not directly accessible from the internet
- **ECS Tasks**: In public subnets for outbound internet access (image pulls, API calls)
  - Security group restricts ingress to ALB security group only
  - Not directly accessible from the internet
- **API Gateway**: Public endpoint (AWS-managed)
  - Routes traffic via VPC Link to internal ALB
  - All traffic must go through API Gateway


This architecture ensures:
- ALB cannot be directly accessed from the internet
- All traffic is routed through API Gateway (enabling rate limiting, API keys, etc.)
- Defense in depth: multiple layers of security (API Gateway + VPC Link + Security Groups)

### ECS Tasks in Public Subnets: Intentional Trade-off

**Current Design**: ECS tasks are deployed in public subnets with public IPs assigned.

**Why Public Subnets?**
- **Simplicity**: No NAT Gateway setup required (saves ~$32/month + complexity)
- **Cost-effective**: Avoids NAT Gateway charges for a take-home project
- **Sufficient security**: Security groups prevent inbound internet access (only ALB can reach tasks)
- **Outbound access**: Tasks can pull container images from ECR and send logs to CloudWatch

**Trade-offs:**
- ✅ **Pros**: Simple, cost-effective, works well for MVP/take-home projects
- ⚠️ **Cons**: Tasks have public IPs (though not accessible due to security groups), less "textbook" architecture

**Production Alternative:**
For production workloads, consider moving ECS tasks to private subnets with NAT Gateway:
- Tasks would have private IPs only (no public IPs)
- More secure network isolation
- Additional cost: ~$32/month per NAT Gateway + data transfer charges
- Requires NAT Gateway setup in Terraform

**Security Note:**
While tasks have public IPs, they are **not accessible from the internet** because:
- Security group only allows ingress from ALB security group
- No inbound rules allowing `0.0.0.0/0`
- Tasks can only be reached via: Internet → API Gateway → VPC Link → ALB → Tasks

This is an acceptable trade-off for a take-home project where simplicity and cost-effectiveness outweigh the added complexity of NAT Gateway setup.

---

## Runtime configuration notes

### Auth keys
The ECS task passes:
- `API_KEYS_JSON` from Terraform var `api_keys_json`

Example format:
```json
{"key_admin":["t1"],"key_t1":["t1"]}
```

### Database (current behavior)
The ECS task currently sets:
- `DB_PATH` (SQLite), e.g. `/tmp/app.db` or `./data/app.db`

Important:
- With SQLite in a container, storage is **ephemeral** (lost when task is replaced).
- This is acceptable for the take-home MVP deployment demonstration, but not production.

### RDS wiring (documented)
RDS Postgres is provisioned to satisfy requirements and represent production storage.
A production wiring approach would be:
- Store credentials in Secrets Manager/SSM
- Pass connection info to the task as env var(s), e.g.:
  - `DATABASE_URL=postgresql://...`
  - or `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`
- Update the application DB layer to use Postgres instead of SQLite.

This repo may include RDS resources even if the running container still uses SQLite.

---

## Scaling strategy

### ECS service scaling (implemented)
- ECS Service Auto Scaling via target tracking:
  - CPU target (e.g., 60%)
  - Memory target (e.g., 70%)
- Capacity bounds:
  - `autoscale_min` (keep at least 1 task)
  - `autoscale_max` (cap to control cost)

### Load balancing
- ALB distributes traffic across tasks in the target group.
- Health checks automatically remove unhealthy tasks.

### Data tier scaling (documented)
For production:
- Scale RDS instance class vertically; add read replicas as needed.
- Add alarms on CPU/storage/connections and tune connection pooling.

---

## Monitoring and observability

### Logging
- ECS container logs go to a CloudWatch Log Group (retention via `log_retention_days`).
- The app also exposes operational metrics at:
  - `GET /api/v1/metrics`

### Alarms (implemented)
Typical alarms included:
- ECS CPU high
- ECS memory high
- ALB 5xx elevated
- RDS CPU/storage issues

`alarm_actions` may be empty by default (no notifications). In production, wire to SNS/PagerDuty/Slack.

---

## Blue/green deployment strategy

### Preferred (production-grade): ECS + CodeDeploy blue/green
- Use CodeDeploy ECS deployment group
- ALB has two target groups: **blue** and **green**
- Traffic shifts gradually from blue → green
- Automatic rollback if:
  - health checks fail
  - alarms trigger during deployment

### Take-home note
To keep IaC minimal, the repository may implement this as:
- A partial/stub `deploy.tf` plus documentation, OR
- Full CodeDeploy resources if time allows.

Either way, the intended approach and rollback plan should be clear.

---

## Cleanup
To delete all resources:
```bash
cd infra/terraform
terraform destroy
```

---

## Files
- `infra/terraform/*.tf`: Terraform resources (networking, ECS, ALB, API Gateway, RDS, IAM, logs/alarms, scaling, blue/green)
- `infra/terraform/terraform.tfvars.example`: example config (copy to `terraform.tfvars`)
- `Dockerfile` (repo root): builds the container image used by ECS
