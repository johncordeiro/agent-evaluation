# Agent Evaluation - Weni Fork

> **Note**: This is a fork of the original [Agent Evaluation framework by AWS Labs](https://github.com/awslabs/agent-evaluation). This fork adds support for testing [Weni](https://weni.ai) conversational AI agents while maintaining all the original functionality for AWS services.

Agent Evaluation is a generative AI-powered framework for testing virtual agents.

Internally, Agent Evaluation implements an LLM agent ([evaluator](evaluators/index.md)) that will orchestrate conversations with your own agent ([target](targets/index.md)) and evaluate the responses during the conversation.

## ✨ Key features

- **🆕 Weni Agent Support**: Built-in support for testing [Weni](https://weni.ai) conversational AI agents through their API and WebSocket interface.
- Built-in support for popular AWS services including [Amazon Bedrock](https://aws.amazon.com/bedrock/), [Amazon Q Business](https://aws.amazon.com/q/business/), and [Amazon SageMaker](https://aws.amazon.com/sagemaker/). You can also [bring your own agent](targets/custom_targets.md) to test using Agent Evaluation.
- Orchestrate concurrent, multi-turn conversations with your agent while evaluating its responses.
- Define [hooks](hooks.md) to perform additional tasks such as integration testing.
- Can be incorporated into CI/CD pipelines to expedite the time to delivery while maintaining the stability of agents in production environments.

## 🚀 Quick Start with Weni

### Installation

Install the package from PyPI:

```bash
pip install weni-agenteval
```

### Prerequisites

!!! warning "Important"
    You need both AWS and Weni credentials to run evaluations!

To test Weni agents, you'll need:

1. **AWS Credentials**: Required for the evaluator (Claude model via Bedrock)
   - AWS Access Key ID
   - AWS Secret Access Key  
   - AWS Session Token

2. **A Weni Project**: An active project in the [Weni platform](https://weni.ai)

3. **Weni Authentication**: Choose one of the following methods:

   **🚀 Option 1: Weni CLI (Recommended)**
   
   Install and authenticate with the Weni CLI:
   ```bash
   # Install Weni CLI
   pip install weni-cli
   
   # Authenticate with Weni
   weni login
   
   # Select your project
   weni project use [your-project-uuid]
   ```
   
   **📋 Option 2: Environment Variables**
   
   Set these environment variables manually:
   - `WENI_PROJECT_UUID`: Your project's unique identifier
   - `WENI_BEARER_TOKEN`: Your authentication bearer token

### Basic Usage

Create a test configuration file `agenteval.yml`:

```yaml
evaluator:
  model: claude-haiku-3_5-us
  aws_region: us-east-1

target:
  type: weni
  timeout: 30      # Optional: max seconds to wait for response

tests:
  greeting:
    steps:
      - Send a greeting "Olá, bom dia!"
      - Ask what "com oq vc pode me ajudar?"
    expected_results:
      - Agent responds with a friendly greeting
      - Agent shows up a menu with options to help the user

  purchase_outside_postal_code:
    steps:
      - Ask information "quero comprar arroz"
      - Give the postal code "04538-132"
    expected_results:
      - Agent responds asking for postal code
      - Agent says it doesn't deliver to this postal code
```

Run the evaluation:

```bash
weni-agenteval run
```

---

<div class="grid cards" markdown>

-   🚀 __Getting started__

    ---

    Create your first Weni agent test.

    [:octicons-arrow-right-24: User Guide](user_guide.md#getting-started)

-   🎯 __Weni Target Configuration__

    ---

    Learn how to configure your Weni agent for testing.

    [:octicons-arrow-right-24: Weni Target](targets/weni.md)

-   ✏️ __Writing test cases__

    ---

    Learn how to write effective test cases for conversational AI.

    [:octicons-arrow-right-24: User Guide](user_guide.md#writing-test-cases)

-   :material-github:{ .lg .middle } __Contribute__

    ---
    Review the contributing guidelines to get started!

    [:octicons-arrow-right-24: GitHub](https://github.com/weni-ai/agent-evaluation/blob/main/CONTRIBUTING.md)


</div>