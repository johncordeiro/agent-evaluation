# Installation

Agent Evaluation requires `python>=3.9`. Please make sure you have an acceptable version of Python before proceeding.

## Install from PyPI (Recommended)

```bash
pip install weni-agenteval
```

## Install from Source

You can also install from source by cloning the [repository](https://github.com/weni-ai/agent-evaluation) and installing from the project root.

```bash
git clone https://github.com/weni-ai/agent-evaluation.git
cd agent-evaluation
pip install -e .
```

## Prerequisites for Weni Target

!!! warning "Important"
    You need both AWS and Weni credentials to run evaluations!

### AWS Credentials (Required for Evaluator)

The evaluator uses Amazon Bedrock's Claude models, so you'll need:

- AWS Access Key ID
- AWS Secret Access Key
- AWS Session Token

Set these as environment variables:

**macOS/Linux:**
```bash
export AWS_ACCESS_KEY_ID="your-aws-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-access-key"
export AWS_SESSION_TOKEN="your-aws-session-token"
```

**Windows (Command Prompt):**
```cmd
set AWS_ACCESS_KEY_ID=your-aws-access-key-id
set AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
set AWS_SESSION_TOKEN=your-aws-session-token
```

**Windows (PowerShell):**
```powershell
$env:AWS_ACCESS_KEY_ID="your-aws-access-key-id"
$env:AWS_SECRET_ACCESS_KEY="your-aws-secret-access-key"
$env:AWS_SESSION_TOKEN="your-aws-session-token"
```

### Weni Authentication

Choose one of the following authentication methods:

#### Option 1: Weni CLI (Recommended)

Install and authenticate with the Weni CLI:

```bash
# Install Weni CLI
pip install weni-cli

# Authenticate with Weni
weni login

# Select your project
weni project use [your-project-uuid]
```

Get the Weni CLI from: https://github.com/weni-ai/weni-cli

#### Option 2: Environment Variables

If you prefer not to use the Weni CLI, set these environment variables:

**macOS/Linux:**
```bash
export WENI_PROJECT_UUID="your-project-uuid-here"
export WENI_BEARER_TOKEN="your-bearer-token-here"
```

**Windows (Command Prompt):**
```cmd
set WENI_PROJECT_UUID=your-project-uuid-here
set WENI_BEARER_TOKEN=your-bearer-token-here
```

**Windows (PowerShell):**
```powershell
$env:WENI_PROJECT_UUID="your-project-uuid-here"
$env:WENI_BEARER_TOKEN="your-bearer-token-here"
```

#### Option 3: Configuration File

You can also provide credentials directly in your test configuration file (not recommended for production):

```yaml
target:
  type: weni
  weni_project_uuid: your-project-uuid-here
  weni_bearer_token: your-bearer-token-here
```

## Verify Installation

After installation, verify that everything works:

```bash
weni-agenteval --help
```

You should see the help message with available commands and options.