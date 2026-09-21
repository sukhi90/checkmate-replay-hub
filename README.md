## Milestone 1 Result

The Checkmate Replay Hub frontend is deployed automatically from GitHub.

### CI/CD Flow

GitHub
→ AWS CodePipeline
→ AWS CodeBuild
→ Amazon S3

A change pushed to the `main` branch automatically starts the pipeline and deploys the updated frontend.

### Infrastructure as Code

The AWS infrastructure is defined in:

`infrastructure/template.yaml`

The following resources are managed through CloudFormation:

- S3 website bucket
- S3 artifact bucket
- CodeBuild project
- CodePipeline
- IAM roles
