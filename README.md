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

Set the environment variables listed in the **Environment variables reference** section below, then start the app with:

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

## Azure AI Foundry: creating the agent

1. Open [Azure AI Foundry](https://ai.azure.com) and navigate to your project.
2. In the left sidebar choose **Agents** → **New agent**.
3. Give the agent a name (e.g. `CRM Fabric Assistant`).
4. Paste a system prompt that tells the agent to use both sources, for example:

   ```text
   You are a CRM sales assistant with access to live Fabric Lakehouse data.
   When the user asks about a customer, account, or deal, always query the
   connected Fabric tools first and cite the data in your reply.
   Use the [SYSTEM CONTEXT] block prepended to each conversation to understand
   which CRM record the user is currently viewing.
   ```

5. Note the **Agent ID** shown in the agent detail panel — this is your `AZURE_AI_AGENT_ID`.

---

## Connecting Microsoft Fabric Lakehouse to the Foundry agent

### 1. Enable the Fabric Data Agent in Microsoft Fabric

1. Open your Microsoft Fabric workspace.
2. Navigate to the Lakehouse you want to expose.
3. In the Lakehouse toolbar select **New** → **Data agent** (preview).
4. Choose the tables or semantic models the agent should be able to query, then save.
5. Publish the Data Agent — Fabric generates an endpoint URL and an **agent name** you will need in the next step.

### 2. Add the Fabric Data Agent as a tool in Azure AI Foundry

1. In AI Foundry, open your agent and scroll to the **Tools** section.
2. Click **Add tool** → **Microsoft Fabric**.
3. Enter the Fabric Data Agent endpoint URL and authenticate with the same identity that owns the workspace (service principal or managed identity both work).
4. Give the tool a short description that matches what you put in the system prompt (e.g. *"Query Fabric Lakehouse for customer and deal data"*).
5. Save the agent.  Foundry will now call the Fabric Data Agent automatically whenever the LLM decides the tool is needed.

### 3. Grant your app identity access to Fabric

The FastAPI app authenticates via `DefaultAzureCredential` (managed identity, environment credential, or Azure CLI).  That identity must have:

| Resource | Required role |
|---|---|
| Azure AI Foundry project | **Azure AI Developer** |
| Fabric workspace | **Contributor** (or a custom role with *Read* + *Execute* on the Data Agent) |

Assign roles in the Azure portal (IAM blade for the AI Foundry project) and in the Fabric workspace settings (**Manage access**).

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | ✅ | Full endpoint URL of your AI Foundry project, e.g. `https://<project>.services.ai.azure.com/api/projects/<project>` |
| `AZURE_AI_AGENT_ID` | ✅ | Agent ID copied from the Foundry Agents panel |
| `CRM_ALLOWED_ORIGINS` | Recommended | Comma-separated list of CRM hostnames allowed to embed the widget, e.g. `https://crm.contoso.com` |

---

## Security notes

- Keep Azure credentials and agent identifiers on the server only.
- Restrict `CRM_ALLOWED_ORIGINS` to trusted CRM hosts instead of using `*`.
- Prefer sending only the CRM fields the agent needs, rather than the entire page DOM.
