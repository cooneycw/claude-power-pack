"""Infrastructure as Code scaffold generation and discovery.

Provides:
- Scaffold generation for tiered IaC directories (foundation/platform/app)
- Cloud resource discovery via CLI tools (aws/az/gcloud)
- IaC pipeline generation with approval gates
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import InfrastructureConfig
from .models import CloudProvider, IaCProvider


def scaffold_infrastructure(
    project_root: str | Path,
    config: Optional[InfrastructureConfig] = None,
    output_dir: Optional[str | Path] = None,
) -> dict[str, str]:
    """Generate IaC scaffold with tiered directory structure.

    Creates:
        infra/
            foundation/  (subscriptions, resource groups, DNS, networking)
            platform/    (registries, key vaults, shared DBs)
            app/         (app-specific infra)

    Args:
        project_root: Path to project root.
        config: Infrastructure configuration (defaults used if None).
        output_dir: Where to write files (None = dry run, returns content).

    Returns:
        Dict mapping filepath to content for each generated file.
    """
    if config is None:
        config = InfrastructureConfig()

    provider = IaCProvider(config.provider)
    cloud = CloudProvider(config.cloud)

    generators = {
        IaCProvider.TERRAFORM: _scaffold_terraform,
        IaCProvider.PULUMI: _scaffold_pulumi,
        IaCProvider.BICEP: _scaffold_bicep,
    }

    generator = generators.get(provider, _scaffold_terraform)
    files = generator(config, cloud)

    if output_dir:
        root = Path(output_dir)
        for filepath, content in files.items():
            full_path = root / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    return files


def generate_infra_pipeline(
    config: Optional[InfrastructureConfig] = None,
    provider: str = "github-actions",
    output_dir: Optional[str | Path] = None,
) -> dict[str, str]:
    """Generate CI/CD pipelines for infrastructure tiers.

    Foundation tier gets manual approval gates.
    Platform tier may or may not require approval.
    App tier runs automatically.

    Args:
        config: Infrastructure configuration.
        provider: Pipeline provider (github-actions or woodpecker).
        output_dir: Where to write files (None = dry run).

    Returns:
        Dict mapping filepath to content.
    """
    if config is None:
        config = InfrastructureConfig()

    iac = IaCProvider(config.provider)

    if provider == "github-actions":
        files = _generate_gh_infra_pipeline(config, iac)
    else:
        files = _generate_woodpecker_infra_pipeline(config, iac)

    if output_dir:
        root = Path(output_dir)
        for filepath, content in files.items():
            full_path = root / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    return files


def generate_discovery_script(
    cloud: str = "aws",
    output_dir: Optional[str | Path] = None,
) -> dict[str, str]:
    """Generate a cloud resource discovery script.

    Creates a shell script that audits existing cloud resources
    and outputs them in a format suitable for IaC import.

    Args:
        cloud: Cloud provider (aws, azure, gcp).
        output_dir: Where to write files (None = dry run).

    Returns:
        Dict mapping filepath to content.
    """
    generators = {
        "aws": _generate_aws_discovery,
        "azure": _generate_azure_discovery,
        "gcp": _generate_gcp_discovery,
    }

    generator = generators.get(cloud, _generate_aws_discovery)
    files = generator()

    if output_dir:
        root = Path(output_dir)
        for filepath, content in files.items():
            full_path = root / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            if filepath.endswith(".sh"):
                full_path.chmod(0o755)

    return files


# --- Terraform scaffolding ---


def _scaffold_terraform(config: InfrastructureConfig, cloud: CloudProvider) -> dict[str, str]:
    """Generate Terraform scaffold."""
    files: dict[str, str] = {}

    # Provider block
    provider_block = _tf_provider_block(cloud)
    backend_block = _tf_backend_block(config)
    tags_block = _tf_tags_block(config)

    # Foundation tier
    files["infra/foundation/main.tf"] = f"""\
# Foundation Layer — run once, touch rarely
# Resources: subscriptions, resource groups, DNS zones, networking, identity
#
# Deploy with approval: terraform plan -> review -> terraform apply
{provider_block}
{backend_block}

# Add foundation resources here:
# - DNS zones
# - Resource groups / VPCs
# - Identity providers
# - Networking (VNets, subnets, peering)
"""

    files["infra/foundation/variables.tf"] = """\
# Foundation variables

variable "project_name" {
  description = "Project name for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "region" {
  description = "Primary cloud region"
  type        = string
}
"""

    files["infra/foundation/outputs.tf"] = """\
# Foundation outputs — consumed by platform and app tiers
# Use terraform_remote_state to reference these from other tiers
"""

    files["infra/foundation/tags.tf"] = tags_block

    # Platform tier
    files["infra/platform/main.tf"] = f"""\
# Platform Layer — shared services
# Resources: container registries, key vaults, log analytics, shared DBs
{provider_block}
{backend_block}

# Reference foundation outputs:
# data "terraform_remote_state" "foundation" {{
#   backend = "{config.state_backend.type or 's3'}"
#   config = {{
#     bucket = "{config.state_backend.bucket or 'my-tf-state'}"
#     key    = "foundation/terraform.tfstate"
#   }}
# }}
"""

    files["infra/platform/variables.tf"] = """\
variable "project_name" {
  description = "Project name for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}
"""

    # App tier
    files["infra/app/main.tf"] = f"""\
# Application Layer — app-specific infrastructure
# Resources: app services, functions, storage, app databases
{provider_block}
{backend_block}

# Reference platform outputs:
# data "terraform_remote_state" "platform" {{
#   backend = "{config.state_backend.type or 's3'}"
#   config = {{
#     bucket = "{config.state_backend.bucket or 'my-tf-state'}"
#     key    = "platform/terraform.tfstate"
#   }}
# }}
"""

    files["infra/app/variables.tf"] = """\
variable "project_name" {
  description = "Project name for resource naming and tagging"
  type        = string
}

variable "environment" {
  description = "Environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}
"""

    # Root Makefile for infra operations
    files["infra/Makefile"] = """\
.PHONY: init-foundation plan-foundation apply-foundation \\
        init-platform plan-platform apply-platform \\
        init-app plan-app apply-app

## Foundation (manual approval required)

init-foundation:
\tcd foundation && terraform init

plan-foundation:
\tcd foundation && terraform plan -out=tfplan

apply-foundation:
\t@echo "FOUNDATION TIER: Requires manual review of plan output."
\t@echo "Run 'make plan-foundation' first, then approve below."
\tcd foundation && terraform apply tfplan

## Platform (shared services)

init-platform:
\tcd platform && terraform init

plan-platform:
\tcd platform && terraform plan -out=tfplan

apply-platform:
\tcd platform && terraform apply tfplan

## App (application-specific)

init-app:
\tcd app && terraform init

plan-app:
\tcd app && terraform plan -out=tfplan

apply-app:
\tcd app && terraform apply tfplan

## All tiers

init-all: init-foundation init-platform init-app

plan-all: plan-foundation plan-platform plan-app
"""

    # .gitignore for infra
    files["infra/.gitignore"] = """\
# Terraform
.terraform/
*.tfstate
*.tfstate.backup
*.tfplan
tfplan
.terraform.lock.hcl
crash.log

# Secrets
*.tfvars
!example.tfvars
"""

    # README
    files["infra/README.md"] = f"""\
# Infrastructure as Code

Three-tier infrastructure managed by {config.provider.capitalize()}.

## Tiers

- **foundation/** — Run once, touch rarely. DNS, networking, identity. Manual approval required.
- **platform/** — Shared services. Container registries, key vaults, shared DBs.
- **app/** — Application-specific infrastructure. Deployed with application CI/CD.

## Quick Start

```bash
# Initialize all tiers
make init-all

# Plan and apply foundation (requires manual approval)
make plan-foundation
# Review the plan output carefully
make apply-foundation

# Plan and apply platform
make plan-platform
make apply-platform

# Plan and apply app
make plan-app
make apply-app
```

## State

Remote state backend: {config.state_backend.type or 'configure in backend block'}
Each tier has its own state file to minimize blast radius.

## Tagging

All resources are tagged with:
- `managed-by: {config.tagging.managed_by}`
- `repo: {config.tagging.repo or '<your-repo>'}`
- `owner: {config.tagging.owner or '<your-team>'}`
"""

    return files


def _tf_provider_block(cloud: CloudProvider) -> str:
    providers = {
        CloudProvider.AWS: 'provider "aws" {\n  region = var.region\n}',
        CloudProvider.AZURE: 'provider "azurerm" {\n  features {}\n}',
        CloudProvider.GCP: 'provider "google" {\n  project = var.project_id\n  region  = var.region\n}',
    }
    return providers.get(cloud, providers[CloudProvider.AWS])


def _tf_backend_block(config: InfrastructureConfig) -> str:
    if not config.state_backend.type:
        return "# Configure remote state backend:\n# terraform {\n#   backend \"s3\" { ... }\n# }"

    backends = {
        "s3": f"""\
terraform {{
  backend "s3" {{
    bucket = "{config.state_backend.bucket}"
    key    = "TIER/terraform.tfstate"  # Replace TIER with foundation/platform/app
    region = "{config.state_backend.region or 'us-east-1'}"
    encrypt = true
    dynamodb_table = "{config.state_backend.bucket}-locks"
  }}
}}""",
        "azure-storage": f"""\
terraform {{
  backend "azurerm" {{
    storage_account_name = "{config.state_backend.bucket}"
    container_name       = "tfstate"
    key                  = "TIER/terraform.tfstate"
  }}
}}""",
        "gcs": f"""\
terraform {{
  backend "gcs" {{
    bucket = "{config.state_backend.bucket}"
    prefix = "TIER"
  }}
}}""",
    }
    return backends.get(config.state_backend.type, backends["s3"])


def _tf_tags_block(config: InfrastructureConfig) -> str:
    tags = {
        "managed-by": config.tagging.managed_by,
        "repo": config.tagging.repo or "REPO_NAME",
        "owner": config.tagging.owner or "TEAM_NAME",
    }
    tags.update(config.tagging.extra_tags)

    tag_lines = "\n".join(f'    "{k}" = "{v}"' for k, v in tags.items())
    return f"""\
# Default tags applied to all resources
locals {{
  default_tags = {{
{tag_lines}
  }}
}}
"""


# --- Pulumi scaffolding ---


def _scaffold_pulumi(config: InfrastructureConfig, cloud: CloudProvider) -> dict[str, str]:
    """Generate Pulumi scaffold (Python)."""
    files: dict[str, str] = {}

    runtime = "python"
    cloud_pkg = {
        CloudProvider.AWS: "pulumi-aws",
        CloudProvider.AZURE: "pulumi-azure-native",
        CloudProvider.GCP: "pulumi-gcp",
    }.get(cloud, "pulumi-aws")

    for tier in ("foundation", "platform", "app"):
        files[f"infra/{tier}/Pulumi.yaml"] = f"""\
name: {tier}
runtime: {runtime}
description: {tier.capitalize()} tier infrastructure
"""

        files[f"infra/{tier}/__main__.py"] = f"""\
\"\"\"
{tier.capitalize()} tier infrastructure.
\"\"\"
import pulumi

# Add {tier} resources here
pulumi.export("tier", "{tier}")
"""

        files[f"infra/{tier}/requirements.txt"] = f"""\
pulumi>=3.0.0
{cloud_pkg}
"""

    files["infra/README.md"] = f"""\
# Infrastructure as Code (Pulumi)

Three-tier infrastructure managed by Pulumi ({runtime}).

## Tiers

- **foundation/** — DNS, networking, identity. Manual approval required.
- **platform/** — Shared services.
- **app/** — Application-specific infrastructure.

## Quick Start

```bash
cd infra/foundation && pulumi up --yes
cd infra/platform && pulumi up --yes
cd infra/app && pulumi up --yes
```
"""

    files["infra/.gitignore"] = """\
# Pulumi
*.pyc
__pycache__/
venv/
"""

    return files


# --- Bicep scaffolding ---


def _scaffold_bicep(config: InfrastructureConfig, cloud: CloudProvider) -> dict[str, str]:
    """Generate Bicep scaffold."""
    files: dict[str, str] = {}

    for tier in ("foundation", "platform", "app"):
        files[f"infra/{tier}/main.bicep"] = f"""\
// {tier.capitalize()} tier infrastructure
// Deploy: az deployment sub create --location <region> --template-file main.bicep

targetScope = 'subscription'

param location string = 'canadacentral'
param projectName string

// Add {tier} resources here
"""

        files[f"infra/{tier}/parameters.json"] = """\
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "projectName": {
      "value": "my-project"
    }
  }
}
"""

    files["infra/README.md"] = """\
# Infrastructure as Code (Bicep)

Three-tier infrastructure managed by Azure Bicep.

## Tiers

- **foundation/** — Resource groups, DNS, VNets. Manual approval required.
- **platform/** — Key Vault, ACR, Log Analytics.
- **app/** — App Service, Functions, Storage.

## Quick Start

```bash
az deployment sub create --location canadacentral --template-file infra/foundation/main.bicep
az deployment sub create --location canadacentral --template-file infra/platform/main.bicep
az deployment sub create --location canadacentral --template-file infra/app/main.bicep
```
"""

    files["infra/.gitignore"] = """\
# Bicep
*.json.bak
"""

    return files


# --- Pipeline generation ---


def _generate_gh_infra_pipeline(
    config: InfrastructureConfig,
    iac: IaCProvider,
) -> dict[str, str]:
    """Generate GitHub Actions workflows for infrastructure tiers."""
    files: dict[str, str] = {}

    plan_cmd = {
        IaCProvider.TERRAFORM: "terraform plan -out=tfplan",
        IaCProvider.PULUMI: "pulumi preview",
        IaCProvider.BICEP: "az deployment sub what-if --location ${{ vars.AZURE_LOCATION }} --template-file main.bicep",
    }.get(iac, "terraform plan -out=tfplan")

    apply_cmd = {
        IaCProvider.TERRAFORM: "terraform apply tfplan",
        IaCProvider.PULUMI: "pulumi up --yes",
        IaCProvider.BICEP: "az deployment sub create --location ${{ vars.AZURE_LOCATION }} --template-file main.bicep",
    }.get(iac, "terraform apply tfplan")

    init_cmd = {
        IaCProvider.TERRAFORM: "terraform init",
        IaCProvider.PULUMI: "pip install -r requirements.txt",
        IaCProvider.BICEP: "az bicep install",
    }.get(iac, "terraform init")

    for tier_name, tier_cfg in config.tiers.items():
        lines: list[str] = []
        lines.append(f"# Infrastructure: {tier_name} tier")
        lines.append("# Generated by Claude Power Pack /cicd:infra-pipeline")
        lines.append("")
        lines.append(f"name: 'Infra: {tier_name.capitalize()}'")
        lines.append("")
        lines.append("on:")
        lines.append("  push:")
        lines.append(f"    paths: ['infra/{tier_name}/**']")
        lines.append("    branches: [main]")
        lines.append("  pull_request:")
        lines.append(f"    paths: ['infra/{tier_name}/**']")
        lines.append("    branches: [main]")
        lines.append("  workflow_dispatch:")
        lines.append("")
        lines.append("jobs:")

        # Plan job (always runs)
        lines.append("  plan:")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    steps:")
        lines.append("      - uses: actions/checkout@v4")
        lines.append("      - name: Init")
        lines.append(f"        working-directory: infra/{tier_name}")
        lines.append(f"        run: {init_cmd}")
        lines.append("      - name: Plan")
        lines.append(f"        working-directory: infra/{tier_name}")
        lines.append(f"        run: {plan_cmd}")
        lines.append("")

        # Apply job
        lines.append("  apply:")
        lines.append("    needs: plan")
        lines.append("    runs-on: ubuntu-latest")
        lines.append("    if: github.ref == 'refs/heads/main' && github.event_name == 'push'")

        if tier_cfg.approval_required:
            lines.append(f"    environment: infra-{tier_name}")  # Requires environment approval

        lines.append("    steps:")
        lines.append("      - uses: actions/checkout@v4")
        lines.append("      - name: Init")
        lines.append(f"        working-directory: infra/{tier_name}")
        lines.append(f"        run: {init_cmd}")
        lines.append("      - name: Plan")
        lines.append(f"        working-directory: infra/{tier_name}")
        lines.append(f"        run: {plan_cmd}")
        lines.append("      - name: Apply")
        lines.append(f"        working-directory: infra/{tier_name}")
        lines.append(f"        run: {apply_cmd}")
        lines.append("")

        files[f".github/workflows/infra-{tier_name}.yml"] = "\n".join(lines)

    return files


def _generate_woodpecker_infra_pipeline(
    config: InfrastructureConfig,
    iac: IaCProvider,
) -> dict[str, str]:
    """Generate Woodpecker CI pipeline for infrastructure."""
    files: dict[str, str] = {}

    image = {
        IaCProvider.TERRAFORM: "hashicorp/terraform:latest",
        IaCProvider.PULUMI: "pulumi/pulumi-python:latest",
        IaCProvider.BICEP: "mcr.microsoft.com/azure-cli:latest",
    }.get(iac, "hashicorp/terraform:latest")

    for tier_name, tier_cfg in config.tiers.items():
        lines = [
            f"# Infrastructure: {tier_name} tier",
            "# Generated by Claude Power Pack /cicd:infra-pipeline",
            "",
            "when:",
            f"  path: 'infra/{tier_name}/**'",
            "  branch: main",
            "  event: [push, pull_request]",
            "",
            "steps:",
            f"  - name: plan-{tier_name}",
            f"    image: {image}",
            "    commands:",
            f"      - cd infra/{tier_name}",
            "      - terraform init",
            "      - terraform plan -out=tfplan",
            "",
        ]

        if not tier_cfg.approval_required:
            lines.extend([
                f"  - name: apply-{tier_name}",
                f"    image: {image}",
                "    commands:",
                f"      - cd infra/{tier_name}",
                "      - terraform init",
                "      - terraform apply tfplan",
                "    when:",
                "      branch: main",
                "      event: push",
                "",
            ])

        files[f".woodpecker/infra-{tier_name}.yml"] = "\n".join(lines)

    return files


# --- Discovery scripts ---


def _generate_aws_discovery() -> dict[str, str]:
    return {
        "infra/scripts/discover-aws.sh": """\
#!/usr/bin/env bash
# AWS Resource Discovery Script
# Generated by Claude Power Pack /cicd:infra-discover
#
# Outputs a manifest of existing AWS resources for IaC import.
# Requires: aws CLI configured with appropriate permissions.

set -euo pipefail

echo "=== AWS Resource Discovery ==="
echo "Account: $(aws sts get-caller-identity --query Account --output text)"
echo "Region: $(aws configure get region)"
echo ""

echo "--- VPCs ---"
aws ec2 describe-vpcs --query 'Vpcs[].{ID:VpcId,CIDR:CidrBlock,Name:Tags[?Key==`Name`].Value|[0]}' --output table

echo ""
echo "--- Route53 Hosted Zones ---"
aws route53 list-hosted-zones --query 'HostedZones[].{Name:Name,ID:Id,Records:ResourceRecordSetCount}' --output table

echo ""
echo "--- IAM Roles ---"
aws iam list-roles \\
  --query 'Roles[?starts_with(RoleName,`custom-`)||starts_with(RoleName,`app-`)].{Name:RoleName,Created:CreateDate}' \\
  --output table

echo ""
echo "--- RDS Instances ---"
aws rds describe-db-instances \\
  --query 'DBInstances[].{ID:DBInstanceIdentifier,Engine:Engine,Status:DBInstanceStatus,Class:DBInstanceClass}' \\
  --output table

echo ""
echo "--- S3 Buckets ---"
aws s3api list-buckets --query 'Buckets[].{Name:Name,Created:CreationDate}' --output table

echo ""
echo "--- ECS Clusters ---"
aws ecs list-clusters --query 'clusterArns' --output table

echo ""
echo "--- ElastiCache ---"
aws elasticache describe-cache-clusters \\
  --query 'CacheClusters[].{ID:CacheClusterId,Engine:Engine,Status:CacheClusterStatus}' \\
  --output table

echo ""
echo "=== Discovery Complete ==="
echo "To import resources into Terraform:"
echo "  terraform import aws_vpc.main <vpc-id>"
echo "  terraform import aws_route53_zone.main <zone-id>"
""",
    }


def _generate_azure_discovery() -> dict[str, str]:
    return {
        "infra/scripts/discover-azure.sh": """\
#!/usr/bin/env bash
# Azure Resource Discovery Script
# Generated by Claude Power Pack /cicd:infra-discover
#
# Outputs a manifest of existing Azure resources for IaC import.
# Requires: az CLI logged in with appropriate permissions.

set -euo pipefail

echo "=== Azure Resource Discovery ==="
echo "Subscription: $(az account show --query name -o tsv)"
echo ""

echo "--- Resource Groups ---"
az group list --query '[].{Name:name,Location:location,Tags:tags}' -o table

echo ""
echo "--- DNS Zones ---"
az network dns zone list --query '[].{Name:name,ResourceGroup:resourceGroup,Records:numberOfRecordSets}' -o table

echo ""
echo "--- Virtual Networks ---"
az network vnet list \\
  --query '[].{Name:name,ResourceGroup:resourceGroup,AddressSpace:addressSpace.addressPrefixes[0]}' \\
  -o table

echo ""
echo "--- Key Vaults ---"
az keyvault list --query '[].{Name:name,ResourceGroup:resourceGroup,Location:location}' -o table

echo ""
echo "--- App Services ---"
az webapp list --query '[].{Name:name,ResourceGroup:resourceGroup,State:state,URL:defaultHostName}' -o table

echo ""
echo "--- Container Registries ---"
az acr list --query '[].{Name:name,ResourceGroup:resourceGroup,SKU:sku.name}' -o table

echo ""
echo "--- SQL Servers ---"
az sql server list --query '[].{Name:name,ResourceGroup:resourceGroup,FQDN:fullyQualifiedDomainName}' -o table

echo ""
echo "=== Discovery Complete ==="
echo "To import resources into Terraform:"
echo '  terraform import azurerm_resource_group.main /subscriptions/<sub>/resourceGroups/<rg>'
""",
    }


def _generate_gcp_discovery() -> dict[str, str]:
    return {
        "infra/scripts/discover-gcp.sh": """\
#!/usr/bin/env bash
# GCP Resource Discovery Script
# Generated by Claude Power Pack /cicd:infra-discover
#
# Outputs a manifest of existing GCP resources for IaC import.
# Requires: gcloud CLI configured.

set -euo pipefail

PROJECT=$(gcloud config get-value project)
echo "=== GCP Resource Discovery ==="
echo "Project: $PROJECT"
echo ""

echo "--- VPC Networks ---"
gcloud compute networks list --format="table(name,subnetMode,autoCreateSubnetworks)"

echo ""
echo "--- Cloud DNS Zones ---"
gcloud dns managed-zones list --format="table(name,dnsName,visibility)"

echo ""
echo "--- GKE Clusters ---"
gcloud container clusters list --format="table(name,location,status,currentNodeCount)"

echo ""
echo "--- Cloud SQL ---"
gcloud sql instances list --format="table(name,databaseVersion,region,state)"

echo ""
echo "--- Cloud Storage ---"
gsutil ls -L 2>/dev/null | grep -E "^gs://" || echo "No buckets found"

echo ""
echo "=== Discovery Complete ==="
echo "To import resources into Terraform:"
echo "  terraform import google_compute_network.main projects/$PROJECT/global/networks/<name>"
""",
    }
