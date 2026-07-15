# CRM-Foundry-Fabric

An injectable AI chatbot trained on both the user's live CRM page state and Fabric Lakehouse data through Azure AI Foundry and FastAPI.

## What this repository now provides

- `/api/chat` FastAPI endpoint that accepts:
  - `message`
  - `thread_id`
  - `webpage_context`
- Context injection into the Foundry Agent thread before the user message is sent
- A ready-to-embed iframe widget at:

```text
https://<your-fastapi-host>/static/foundry-chat-widget.html
```

## Backend: FastAPI + Foundry Agent

`app.py` accepts `webpage_context` and forwards it to the Foundry Agent as structured hidden context before the user's prompt.

Set these environment variables before starting the API:

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<your-project>.services.ai.azure.com/api/projects/<your-project>"
export AZURE_AI_AGENT_ID="<your-foundry-agent-id>"
export CRM_ALLOWED_ORIGINS="https://crm.contoso.com"
```

Start the app with:

```bash
uvicorn app:app --reload
```

## CRM iframe integration

Inject this iframe into your existing CRM:

```html
<iframe
  id="foundry-chat-widget"
  src="https://<your-fastapi-host>/static/foundry-chat-widget.html"
  title="Foundry CRM Assistant"
  style="width: 420px; height: 640px; border: 0;"
></iframe>
```

Then push the current CRM record into the iframe with `postMessage`:

```html
<script>
  const foundryFrame = document.getElementById("foundry-chat-widget");

  function publishCrmContext() {
    foundryFrame.contentWindow?.postMessage(
      {
        type: "crm-context",
        payload: {
          current_page_url: window.location.href,
          customer_id: document.getElementById("crm-customer-id")?.innerText || "Unknown",
          customer_name: document.getElementById("crm-customer-name")?.innerText || "Unknown",
          account_manager: document.getElementById("crm-manager")?.innerText || "Unknown",
          current_deal_stage: document.getElementById("crm-stage")?.innerText || "Unknown",
          viewed_at_timestamp: new Date().toISOString()
        }
      },
      "https://<your-fastapi-host>"
    );
  }

  publishCrmContext();
</script>
```

The iframe widget then calls `/api/chat` and includes the live CRM context plus the user's question in every request.

## Security notes

- Keep Azure credentials and agent identifiers on the server only.
- Restrict `CRM_ALLOWED_ORIGINS` to trusted CRM hosts instead of using `*`.
- Prefer sending only the CRM fields the agent needs, rather than the entire page DOM.
