terraform {
  backend "gcs" {
    bucket = "postspot-tf-state"
    prefix = "post-service/env/prod"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.67.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}