#!/bin/bash

# Update Fast Endpoint
vault kv put secret/codetether/endpoints/qwen-fast \
    model_ref="qwen:Qwen3.5-35B-A3B" \
    base_url="http://192.165.134.28:10153/v1" \
    api_key="EMPTY" \
    model_name="Qwen/Qwen3.5-35B-A3B"

# Update Heavy Endpoint
vault kv put secret/codetether/endpoints/qwen-heavy \
    model_ref="qwen:Qwen3.5-122B-A10B" \
    base_url="http://108.231.141.46:16396/v1" \
    api_key="EMPTY" \
    model_name="Qwen/Qwen3.5-122B-A10B"

echo "Vault updated successfully."
