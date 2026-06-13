## MODIFIED Requirements

### Requirement: Interactive setup flow
Setup SHALL follow this sequence: Scout API base URL → branch selection → workspace resolution (local path or git clone) → provider/auth/endpoint → fetch models → filter embed-capable models → user model pick → probe dimensions → prescan → index → agent selection → skill install. Any failure SHALL abort setup with no partial index.

#### Scenario: API URL first
- **WHEN** user runs `scout myapp setup`
- **THEN** first prompt is Scout API base URL

### Requirement: Leave blank to keep API key
When a secret already exists for the selected provider, setup SHALL offer leave blank to keep the existing key. When a model is already configured for that provider, setup SHALL display it in the prompt hint.

#### Scenario: Existing OpenRouter key
- **WHEN** `openrouter_api_key` exists in secrets and user leaves key prompt blank
- **THEN** existing key is retained

#### Scenario: Existing local provider key
- **WHEN** `lmstudio_api_key` exists and user leaves prompt blank
- **THEN** existing key is retained
