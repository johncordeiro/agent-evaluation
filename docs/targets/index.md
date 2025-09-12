# Targets

A target represents the agent you want to test.

## 🆕 Weni Agents (Primary Target)

The **Weni target** is the primary focus of this fork, providing native support for testing [Weni](https://weni.ai) conversational AI agents.

### Quick Start

```yaml title="agenteval.yml"
target:
  type: weni
  timeout: 30      # Optional: max seconds to wait for response
```

### Key Features

- **WebSocket Communication**: Real-time bidirectional communication with Weni agents
- **Session Isolation**: Each test case uses unique contact identifiers for proper conversation isolation
- **Multi-language Support**: Configure language settings for your conversational AI
- **Flexible Authentication**: Support for Weni CLI, environment variables, or configuration file

[:octicons-arrow-right-24: **Learn more about Weni Agents**](weni.md)

---

## AWS Service Targets

For AWS service targets, additional base configurations apply:

!!! info "AWS Credentials"
    This project uses Boto3's credential resolution chain to determine the AWS credentials to use. Please refer to the
    Boto3 [documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) for more details.

```yaml title="agenteval.yml"
target:
  aws_profile: my-profile
  aws_region: us-west-2
  endpoint_url: my-endpoint-url
  max_retry: 10
```

`aws_profile` _(string; optional)_

A profile name that is used to create a Boto3 session.

---

`aws_region` _(string; optional)_

The AWS region that is used to create a Boto3 session.

---

`endpoint_url` _(string; optional)_

The endpoint URL for the AWS service which is used to construct the Boto3 client.

---

`max_retry` _(integer; optional)_

Configures the Boto3 client with the maximum number of retry attempts allowed. The default is `10`.

---

## All Available Targets

### Primary Target
- **[🆕 Weni Agents](weni.md)** - Test Weni conversational AI agents (recommended)

### AWS Service Targets
- [Agents for Amazon Bedrock](bedrock_agents.md)
- [Amazon Bedrock Flows](bedrock_flows.md)
- [Knowledge bases for Amazon Bedrock](bedrock_knowledge_bases.md)
- [Amazon Q for Business](q_business.md)
- [Amazon SageMaker endpoints](sagemaker_endpoints.md)
- [Amazon Lex-v2](lex_v2.md)

### Custom Targets
- [Custom Targets](custom_targets.md) - Build your own target implementation

---