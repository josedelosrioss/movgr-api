#!/bin/bash

# Clean and rebuild
rm -rf .aws-sam
sam build

# Remove boto3/botocore (already in Lambda runtime) and local folders
rm -rf .aws-sam/build/ScraperFunction/boto* .aws-sam/build/ScraperFunction/botocore*
rm -rf .aws-sam/build/ApiFunction/boto* .aws-sam/build/ApiFunction/botocore*
rm -rf .aws-sam/build/*/aws/ .aws-sam/build/*/subida/ .aws-sam/build/*/package/

# Check the size (should be < 50MB each)
du -sh .aws-sam/build/*/

# Deploy
sam deploy --stack-name movgr-metro-api --parameter-overrides Environment=staging
