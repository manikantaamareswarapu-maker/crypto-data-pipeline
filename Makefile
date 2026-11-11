# Vendor Python dependencies into each Lambda directory so Terraform can zip
# them, then run Terraform. Usage: `make build` then `make deploy`.

.PHONY: build deploy destroy

build:
	pip install -r lambdas/ingestion/requirements.txt -t lambdas/ingestion/ --upgrade

deploy: build
	cd infra && terraform init && terraform apply

destroy:
	cd infra && terraform destroy
