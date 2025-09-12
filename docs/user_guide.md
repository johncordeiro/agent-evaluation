## Getting started

To begin, initialize a test plan for your Weni agent.

```bash
weni-agenteval init
```

This will create a configuration file named `agenteval.yml` in the current directory.

```yaml title="agenteval.yml"
evaluator:
  model: claude-haiku-3_5-us
  aws_region: us-east-1
target:
  type: weni
  timeout: 30
tests:
  greeting:
    steps:
    - Send a greeting "Olá, bom dia!"
    expected_results:
    - Agent responds with a friendly greeting
```

Update the `target` configuration for your Weni agent:

- `type`: Must be `"weni"` for Weni agents
- `timeout`: Optional timeout in seconds (defaults to 30)

!!! note
    You need both AWS credentials (for the evaluator) and Weni authentication. See [Installation](installation.md) for setup instructions.

Update `tests` with your test cases. Each test must have the following:

- `steps`: A list of steps you want to perform in your test.
- `expected_results`: A list of expected results for your test.

Once you have updated the test plan, you can run your tests:

!!! warning
    The default [evaluator](evaluators/index.md) is powered by Anthropic's Claude model on Amazon Bedrock. The charges you incur from using Amazon Bedrock will be your responsibility. **Please review [this page](evaluators/index.md#evaluator-costs) on evaluator costs before running your tests.**

```bash
weni-agenteval run
```

The results will be printed in your terminal and a Markdown summary will be available in `agenteval_summary.md`.

You will also find traces saved under `agenteval_traces/`. This is useful for understanding the
flow of evaluation.


## Writing test cases

It is important to be clear and concise when writing your test cases for conversational AI agents.

```yaml title="agenteval.yml"
tests:
  product_inquiry:
    steps:
    - Ask "Quais produtos vocês têm disponíveis?"
    expected_results:
    - Agent provides information about available products
    - Response includes clear product descriptions or categories
```

If your test case is complex, consider breaking it down into multiple, smaller `tests`.

### Multi-turn conversations

To test multiple user-agent interactions, you can provide multiple `steps` to orchestrate the interaction.

```yaml title="agenteval.yml"
tests:
  product_and_delivery:
    steps:
    - Ask "Quais produtos vocês têm?"
    - Ask "Qual é o prazo de entrega?"
    expected_results:
    - Agent provides product information
    - Agent maintains context and provides delivery timeframe
```

The maximum number of turns allowed for a conversation is configured using the `max_turns` parameter for the test (defaults to `2` when not specified).
If the number of turns in the conversation reaches the `max_turns` limit, then the test will fail.

### Providing data

You can test an agent's ability to prompt the user for data when you include it within the step. For example:

```yaml title="agenteval.yml"
tests:
  purchase_with_postal_code:
    steps:
    - Ask "Quero comprar arroz".
      When the agent asks for postal code, respond with "01310-100".
    expected_results:
    - Agent confirms the product selection
    - Agent processes the postal code and confirms delivery availability
```

### Specify the first user message

By default, the first user message in the test is automatically generated based on the first step. To override this message, you can specify the `initial_prompt`.

```yaml title="agenteval.yml"
tests:
  business_hours_inquiry:
    steps:
    - Ask about business hours and weekend availability.
    initial_prompt: Qual é o horário de funcionamento da loja?
    expected_results:
    - Agent provides clear business hours information
    - Agent includes both weekday and weekend hours
```
