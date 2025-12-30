# Cloud Storage Guide: AWS S3 & Cloudflare R2

The Vatican extraction pipeline supports uploading to both **AWS S3** and **Cloudflare R2** (or any S3-compatible storage).

## Quick Start

### Option 1: AWS S3

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
export S3_BUCKET_NAME="vatican-documents"
export AWS_REGION="us-east-1"  # Optional, defaults to us-east-1

# Run extraction with upload
vatican-extract --sections BIBLE --upload
```

### Option 2: Cloudflare R2

```bash
# Set R2 credentials
export R2_ACCESS_KEY_ID="your_r2_access_key"
export R2_SECRET_ACCESS_KEY="your_r2_secret_key"
export R2_ENDPOINT_URL="https://[account-id].r2.cloudflarestorage.com"
export R2_BUCKET_NAME="vatican-documents"

# Run extraction with upload
vatican-extract --sections BIBLE --upload-to-r2
```

## Environment Variables

### AWS S3 Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS secret key | `wJalrXUtnFEMI/...` |
| `S3_BUCKET_NAME` | Yes | S3 bucket name | `vatican-documents` |
| `AWS_REGION` | No | AWS region | `us-east-1` (default) |

**Alternative**: You can also use `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` instead of `AWS_*` variants.

### Cloudflare R2 Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `R2_ACCESS_KEY_ID` | Yes | R2 access key | `your_key` |
| `R2_SECRET_ACCESS_KEY` | Yes | R2 secret key | `your_secret` |
| `R2_ENDPOINT_URL` | Yes | R2 endpoint | `https://abc123.r2.cloudflarestorage.com` |
| `R2_BUCKET_NAME` | Yes | R2 bucket name | `vatican-documents` |

## Storage Structure

Both AWS S3 and R2 use the same organized structure:

```
vatican/
├── bible/
│   ├── bible_3_91264a37.json           # Genesis Ch 1 (complete)
│   ├── bible_3_91264a37.ndjson         # Genesis Ch 1 (chunks)
│   ├── bible_1i_8faeb2c1.json          # Exodus Ch 1
│   └── ...
├── catechism/
│   ├── catechism_of_the_catholic_church.json
│   └── catechism_of_the_catholic_church.ndjson
├── councils/
│   └── ...
├── magisterium/
│   └── ...
└── index.json                           # Master index
```

## AWS S3 Setup

### 1. Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://vatican-documents --region us-east-1
```

Or via AWS Console:
1. Go to S3 Console
2. Click "Create bucket"
3. Name: `vatican-documents`
4. Region: `us-east-1` (or your preferred region)
5. Block public access: Keep enabled (private bucket)
6. Click "Create bucket"

### 2. Create IAM User

1. Go to IAM Console → Users → "Create user"
2. Username: `vatican-extractor`
3. Attach policy: `AmazonS3FullAccess` (or create custom policy below)
4. Create access key → CLI
5. Save Access Key ID and Secret Access Key

**Custom Policy** (recommended - least privilege):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::vatican-documents",
        "arn:aws:s3:::vatican-documents/*"
      ]
    }
  ]
}
```

### 3. Set Environment Variables

```bash
export AWS_ACCESS_KEY_ID="your_access_key_id"
export AWS_SECRET_ACCESS_KEY="your_secret_access_key"
export S3_BUCKET_NAME="vatican-documents"
export AWS_REGION="us-east-1"
```

**Persist in shell profile** (optional):

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export AWS_ACCESS_KEY_ID="your_key"' >> ~/.bashrc
echo 'export AWS_SECRET_ACCESS_KEY="your_secret"' >> ~/.bashrc
echo 'export S3_BUCKET_NAME="vatican-documents"' >> ~/.bashrc
echo 'export AWS_REGION="us-east-1"' >> ~/.bashrc
source ~/.bashrc
```

## Cloudflare R2 Setup

### 1. Create R2 Bucket

1. Go to Cloudflare Dashboard → R2
2. Click "Create bucket"
3. Name: `vatican-documents`
4. Location: Automatic
5. Click "Create bucket"

### 2. Create API Token

1. In R2 dashboard → "Manage R2 API Tokens"
2. Click "Create API token"
3. Token name: `vatican-extractor`
4. Permissions: "Object Read & Write"
5. TTL: Never expire (or set expiration)
6. Click "Create API Token"
7. Save **Access Key ID** and **Secret Access Key**

### 3. Get Endpoint URL

Your R2 endpoint URL format:
```
https://[account-id].r2.cloudflarestorage.com
```

Find your account ID:
- Cloudflare Dashboard → R2 → Settings
- Look for "S3 API endpoint"
- Format: `https://[account-id].r2.cloudflarestorage.com`

### 4. Set Environment Variables

```bash
export R2_ACCESS_KEY_ID="your_access_key_id"
export R2_SECRET_ACCESS_KEY="your_secret_access_key"
export R2_ENDPOINT_URL="https://your-account-id.r2.cloudflarestorage.com"
export R2_BUCKET_NAME="vatican-documents"
```

## Usage Examples

### Extract Bible to AWS S3

```bash
# Set AWS credentials (once)
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export S3_BUCKET_NAME="vatican-documents"

# Extract Bible only
vatican-extract --sections BIBLE --upload --verbose

# Full extraction (all sections)
vatican-extract --upload
```

### Extract Bible to Cloudflare R2

```bash
# Set R2 credentials (once)
export R2_ACCESS_KEY_ID="..."
export R2_SECRET_ACCESS_KEY="..."
export R2_ENDPOINT_URL="https://...r2.cloudflarestorage.com"
export R2_BUCKET_NAME="vatican-documents"

# Extract Bible only
vatican-extract --sections BIBLE --upload-to-r2 --verbose

# Full extraction (all sections)
vatican-extract --upload-to-r2
```

### Multi-Step Workflow

```bash
# Step 1: Discover (instant)
vatican-extract --sections BIBLE --discover-only

# Step 2: Download (~21 min)
vatican-extract --sections BIBLE --download-only

# Step 3: Process locally (~30 min)
vatican-extract --sections BIBLE --process-only

# Step 4: Upload to S3/R2 (~10 min)
vatican-extract --sections BIBLE --upload
```

### Resume Interrupted Upload

```bash
# If upload was interrupted
vatican-extract --resume --upload
```

## Accessing Uploaded Files

### AWS S3 (via AWS CLI)

```bash
# List files
aws s3 ls s3://vatican-documents/vatican/bible/

# Download file
aws s3 cp s3://vatican-documents/vatican/bible/bible_3_91264a37.json .

# Download all Bible files
aws s3 sync s3://vatican-documents/vatican/bible/ ./local_bible/
```

### AWS S3 (via Python)

```python
import boto3

s3 = boto3.client('s3')

# List files
response = s3.list_objects_v2(
    Bucket='vatican-documents',
    Prefix='vatican/bible/'
)

for obj in response.get('Contents', []):
    print(obj['Key'])

# Download file
s3.download_file(
    'vatican-documents',
    'vatican/bible/bible_3_91264a37.ndjson',
    'genesis_1.ndjson'
)
```

### Cloudflare R2 (via AWS CLI)

R2 is S3-compatible, so use AWS CLI with endpoint:

```bash
# Configure AWS CLI for R2
aws configure set aws_access_key_id "$R2_ACCESS_KEY_ID"
aws configure set aws_secret_access_key "$R2_SECRET_ACCESS_KEY"

# List files
aws s3 ls s3://vatican-documents/vatican/bible/ \
  --endpoint-url "$R2_ENDPOINT_URL"

# Download file
aws s3 cp s3://vatican-documents/vatican/bible/bible_3_91264a37.json . \
  --endpoint-url "$R2_ENDPOINT_URL"
```

### Cloudflare R2 (via Python)

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='https://your-account.r2.cloudflarestorage.com',
    aws_access_key_id='your_access_key',
    aws_secret_access_key='your_secret_key'
)

# List files
response = s3.list_objects_v2(
    Bucket='vatican-documents',
    Prefix='vatican/bible/'
)

for obj in response.get('Contents', []):
    print(obj['Key'])
```

## Cost Comparison

### AWS S3 Costs (us-east-1)

**Storage**: ~$0.023/GB/month
- Bible: ~100 MB = **$0.002/month**
- Full archive: ~20 GB = **$0.46/month**

**Upload**: $0.005/1000 PUT requests
- Bible: 2,516 files = **$0.01 one-time**
- Full archive: ~5,000 files = **$0.025 one-time**

**Download**: $0.09/GB (first 10 TB/month)
- Varies by usage

**Total monthly cost** (full archive): ~$0.50/month

### Cloudflare R2 Costs

**Storage**: $0.015/GB/month
- Bible: ~100 MB = **$0.0015/month**
- Full archive: ~20 GB = **$0.30/month**

**Upload**: **$0** (no charges for Class A operations)
**Download**: **$0** (no egress fees)

**Total monthly cost** (full archive): ~$0.30/month

**Winner**: R2 is cheaper (~40% savings) with no egress fees!

## Choosing Between S3 and R2

### Use AWS S3 if:
- You're already using AWS services
- You need tight integration with AWS ecosystem
- You need advanced features (Glacier, Intelligent-Tiering, etc.)
- You have existing AWS credits

### Use Cloudflare R2 if:
- You want lower costs
- You need free egress (no download charges)
- You're using Cloudflare CDN
- You want a simpler pricing model

### Both work identically with the extraction pipeline!

The storage manager uses the same S3 protocol for both, so switching between them is just changing environment variables.

## Troubleshooting

### AWS S3 Issues

**"Access Denied"**:
- Check IAM user has correct permissions
- Verify bucket name is correct
- Ensure region matches bucket region

**"Bucket does not exist"**:
- Create bucket first: `aws s3 mb s3://vatican-documents`
- Check bucket name spelling

**"Credentials not found"**:
- Verify environment variables are set: `echo $AWS_ACCESS_KEY_ID`
- Try: `aws configure` to set credentials system-wide

### R2 Issues

**"Access Denied"**:
- Verify API token has "Object Read & Write" permissions
- Check endpoint URL format is correct
- Ensure Access Key ID and Secret Access Key are correct

**"Endpoint connection error"**:
- Verify endpoint URL includes `https://`
- Check account ID in endpoint URL is correct
- Test: `curl $R2_ENDPOINT_URL` (should return 403, not connection error)

**"InvalidAccessKeyId"**:
- R2 Access Key ID ≠ Cloudflare API Token
- Use the R2-specific API token from "Manage R2 API Tokens"

## Security Best Practices

1. **Never commit credentials** to git
2. **Use .env files** (add to .gitignore)
3. **Rotate keys** periodically
4. **Use least-privilege policies** (limit to specific bucket)
5. **Enable MFA** on AWS/Cloudflare account
6. **Use bucket versioning** (optional, for data protection)
7. **Enable access logging** (optional, for audit trail)

## Next Steps

1. Choose S3 or R2 based on your needs
2. Create bucket and obtain credentials
3. Set environment variables
4. Test with small sample: `vatican-extract --sections BIBLE --limit 5 --upload`
5. Run full extraction: `vatican-extract --sections BIBLE --upload`
