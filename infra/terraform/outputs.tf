output "alb_dns_name" {
  value       = aws_lb.app.dns_name
  description = "Internal ALB DNS name (only accessible via API Gateway VPC Link)"
}

output "apigw_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

