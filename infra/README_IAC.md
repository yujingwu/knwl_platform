## Relationship to Part 2
- Part 2 implements the service logic and runs locally using SQLite (embedded DB).
- Part 3 provides AWS Terraform to deploy the same service as a container with production-oriented infrastructure.
- RDS is provisioned to satisfy Part 3 requirements and represent the production datastore. The app can be configured to use it via environment variables (see `DATABASE_URL`), though local dev continues to default to SQLite.
